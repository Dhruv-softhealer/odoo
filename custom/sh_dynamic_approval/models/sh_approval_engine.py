# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import logging
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval


class ShApprovalEngine(models.AbstractModel):
    """Service model containing approval rule matching and request generation."""

    _name = 'sh.approval.engine'
    _description = 'Dynamic Approval Engine Service'

    @api.model
    def _excluded_models(self):
        """Return models that must never be intercepted by the approval engine."""
        return {
            'sh.approval.type',
            'sh.approval.level',
            'sh.approval.request',
            'sh.approval.line',
            'sh.approval.log',
            'sh.approval.engine',
            'mail.mail',
            'mail.message',
            'mail.activity',
            'ir.attachment',
            'ir.model',
            'ir.model.fields',
            'ir.config_parameter',
            'ir.cron',
            'ir.rule',
            'ir.ui.view',
            'ir.ui.menu',
            'ir.actions.act_window',
            'ir.module.module',
            'ir.model.access',
            'mail.followers',
            'mail.message.subtype',
            'mail.tracking.value',
            'mail.activity.type',
            'bus.presence',
            'bus.bus',
            'res.users.log',
            'res.users',
        }

    @tools.ormcache()
    def _get_models_with_active_approvals(self):
        """Return a set of model names that have active approval types configured."""
        if 'sh.approval.type' in self.env:
            self.env['sh.approval.type'].flush_model(['model', 'active'])
        self.env.cr.execute("SELECT DISTINCT model FROM sh_approval_type WHERE active = true")
        return {row[0] for row in self.env.cr.fetchall() if row[0]}

    @api.model
    def _check_record_locked(self, records, changed_fields=None):
        """Block edits on records with pending approvals unless bypassed by approval internals."""
        if self.env.context.get('sh_skip_dynamic_approval'):
            return
        if not records or records._name in self._excluded_models():
            return
            
        # Fast exit: check if model even has any active approval configurations
        if records._name not in self.sudo()._get_models_with_active_approvals():
            return
            
        # Bypass lock for newly created records to allow initial ORM flushes
        now = fields.Datetime.now()
        existing_records = records.filtered(lambda r: not r.create_date or (now - r.create_date).total_seconds() > 2)
        if not existing_records:
            return

        pending_requests = self.env['sh.approval.request'].sudo().search([
            ('res_model', '=', existing_records._name),
            ('res_id', 'in', existing_records.ids),
            ('state', '=', 'pending'),
        ])
        
        if not pending_requests:
            return
            
        locked_record_ids = set(pending_requests.mapped('res_id'))
        
        if changed_fields:
            # Only allow standard chatter and access fields to be written to avoid crashing mail threads
            allowed_fields = {
                f for f in changed_fields 
                if f.startswith('message_') or f.startswith('activity_') or f in ('access_token', 'access_url')
            }
            # If the write ONLY contains allowed fields, bypass the lock
            if not set(changed_fields) - allowed_fields:
                locked_record_ids.clear()
                    
        if locked_record_ids:
            raise UserError(_('This record is completely locked because it is pending approval. It cannot be modified or processed.'))

    @api.model
    def _trigger_for_records(self, records, event, changed_fields=None):
        """Evaluate configured approval types and create approval requests for matching records."""
        if self.env.context.get('sh_skip_dynamic_approval'):
            return self.env['sh.approval.request']
        if not records or records._name in self._excluded_models():
            return self.env['sh.approval.request']
            
        # Fast exit: check if model even has any active approval configurations
        if records._name not in self.sudo()._get_models_with_active_approvals():
            return self.env['sh.approval.request']
            
        created_requests = self.env['sh.approval.request']
        for record in records:
            approval_type = self._find_applicable_approval_type(record, event=event, changed_fields=changed_fields)
            if not approval_type:
                continue
            existing_request = self.env['sh.approval.request'].sudo().search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
                ('state', '=', 'pending'),
            ], limit=1)
            if existing_request:
                continue
            request = self._create_approval_request(record, approval_type, event=event)
            created_requests |= request
        return created_requests

    @api.model
    def _stage_write_for_approval(self, records, vals, changed_fields=None):
        """Create pending approval requests for write values that must not be applied yet."""
        if self.env.context.get('sh_skip_dynamic_approval'):
            return records.browse(), {}
        if not records or records._name in self._excluded_models():
            return records.browse(), {}
            
        # Fast exit: check if model even has any active approval configurations
        if records._name not in self.sudo()._get_models_with_active_approvals():
            return records.browse(), {}
        staged_records = records.browse()
        staged_fields_by_record = {}
        for record in records:
            approval_type = self._find_applicable_approval_type(record, event='write', changed_fields=changed_fields, proposed_vals=vals)
            if not approval_type:
                continue
            existing_request = self.env['sh.approval.request'].sudo().search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
                ('state', '=', 'pending'),
            ], limit=1)
            if existing_request:
                continue
            
            tracked_fields = set(approval_type.update_field_ids.mapped('name'))
            staged_vals = {k: v for k, v in vals.items() if k in tracked_fields}
            
            if not staged_vals:
                continue

            request = self._create_approval_request(record, approval_type, event='write', staged_vals=staged_vals)
            request._log_event('triggered', _('Update values staged until approval.'))
            staged_records |= record
            staged_fields_by_record[record.id] = list(staged_vals.keys())
        return staged_records, staged_fields_by_record

    @api.model
    def _find_applicable_approval_type(self, record, event=None, changed_fields=None, proposed_vals=None):
        """Return the best matching approval type for one record."""
        approval_types = self.env['sh.approval.type'].sudo().search([
            ('active', '=', True),
            ('model', '=', record._name),
        ], order='sequence, id')
        if event:
            approval_types = approval_types.filtered(lambda item: item.trigger_event in self._trigger_values(event))
        if event == 'write' and changed_fields:
            field_names = set(changed_fields)
            approval_types = approval_types.filtered(
                lambda item: bool(field_names.intersection(set(item.update_field_ids.mapped('name'))))
            )
        company = self._record_company(record)
        matching_types = approval_types.filtered(
            lambda approval_type: approval_type.company_id == company and self._domain_matches(approval_type, record, proposed_vals=proposed_vals)
        )
        return matching_types.sorted(lambda item: (item.sequence, item.id))[:1] if matching_types else self.env['sh.approval.type']

    @api.model
    def _matching_approval_types(self, model_name, event, changed_fields=None):
        """Return active approval types for a model and trigger event."""
        trigger_domain = [('trigger_event', 'in', self._trigger_values(event))]
        domain = [
            ('active', '=', True),
            ('model', '=', model_name),
        ] + trigger_domain
        approval_types = self.env['sh.approval.type'].sudo().search(domain, order='sequence, id')
        if event == 'write' and changed_fields:
            field_names = set(changed_fields)
            approval_types = approval_types.filtered(
                lambda item: bool(field_names.intersection(set(item.update_field_ids.mapped('name'))))
            )
        return approval_types

    @api.model
    def _trigger_values(self, event):
        """Map ORM event to configured trigger values."""
        if event == 'create':
            return ['create', 'both']
        if event == 'write':
            return ['write', 'both']
        return ['manual']

    @api.model
    def _domain_matches(self, approval_type, record, proposed_vals=None):
        """Evaluate an approval type domain against a single record."""
        domain_text = approval_type.domain_filter or '[]'
        domain = Domain(safe_eval(domain_text, {'uid': self.env.uid, 'user': self.env.user}))
        if domain == Domain.TRUE:
            return True
        eval_record = record.with_context(prefetch_fields=False).new(proposed_vals) if proposed_vals else record
        domain.validate(eval_record)
        return bool(eval_record.filtered_domain(domain))

    @api.model
    def _record_company(self, record):
        """Resolve target record company with fallback to current company."""
        if 'company_id' in record._fields and record.company_id:
            return record.company_id
        return self.env.company

    @api.model
    def _create_approval_request(self, record, approval_type, event='create', staged_vals=None):
        """Create and submit an approval request for one target record."""
        request = self.env['sh.approval.request'].sudo().with_context(sh_skip_dynamic_approval=True).create({
            'name': _('%(type)s - %(record)s') % {
                'type': approval_type.name,
                'record': record.display_name,
            },
            'approval_type_id': approval_type.id,
            'company_id': approval_type.company_id.id,
            'res_model': record._name,
            'res_id': record.id,
            'requester_id': self.env.user.id,
            'trigger_event': event,
            'state': 'draft',
        })
        if staged_vals:
            request._set_staged_write_values(staged_vals)
        self._prepare_request_lines(request)
        request.sudo()._log_event('triggered', _('Domain matched. Rule: %s') % approval_type.name)
        request.sudo().action_submit()
        if hasattr(self.env['bus.bus'], '_sendone'):
            self.env['bus.bus'].sudo()._sendone(
                self.env.user.partner_id,
                'simple_notification',
                {
                    'title': _('Approval Triggered'),
                    'message': _('The record %s has been submitted for approval.', record.display_name),
                    'sticky': False,
                    'type': 'info',
                }
            )
        return request

    @api.model
    def _prepare_request_lines(self, request):
        """Create pending approval lines for all configured levels."""
        for level in request.approval_type_id.level_ids.sorted('sequence'):
            if level.company_ids and request.company_id not in level.company_ids:
                continue
            approvers = self._resolve_approvers(level, request._get_target_record(), request.requester_id)
            alternative_user = level.alternative_user_id
            if not approvers and alternative_user:
                approvers = alternative_user
            if not approvers:
                raise UserError(_('No active approver found for approval level %s.') % level.name)
            self.env['sh.approval.line'].sudo().with_context(sh_skip_dynamic_approval=True).create({
                'request_id': request.id,
                'level_id': level.id,
                'sequence': level.sequence,
                'approver_ids': [(6, 0, approvers.ids)],
                'alternative_user_id': alternative_user.id if alternative_user else False,
                'state': request.state,
            })

    @api.model
    def _resolve_approvers(self, level, record, requester):
        """Resolve active approver users for one approval level."""
        record_company = self._record_company(record)
        users = self.env['res.users']
        if level.approval_method == 'group':
            users = level.group_id.sudo().user_ids.filtered(lambda u: not u.company_ids or record_company in u.company_ids)
        elif level.approval_method == 'job':
            employees = self.env['hr.employee'].sudo().search([
                ('job_id', '=', level.job_id.id),
                ('active', '=', True),
                '|', ('company_id', '=', False), ('company_id', '=', record_company.id)
            ])
            users = employees.mapped('user_id') if employees else self.env['res.users']
        elif level.approval_method == 'python':
            localdict = {'record': record, 'env': self.env, 'user': requester}
            try:
                result = safe_eval(level.python_code.strip(), localdict, mode='eval')
                users = self._coerce_users(result)
            except Exception as e:
                _logger.error("Dynamic Approval Engine: Failed to evaluate Python code for level %s. Error: %s", level.name, str(e))
                users = self.env['res.users']
        available_users = users.filtered(lambda user: user.active and not self._is_user_on_leave(user))
        if available_users:
            return available_users
        if level.alternative_user_id:
            return level.alternative_user_id
        return available_users

    @api.model
    def _is_user_on_leave(self, user):
        """Detect whether a user has an approved leave overlapping today."""
        if not user or not user.employee_id or 'hr.leave' not in self.env:
            return False
        today = fields.Date.context_today(self)
        leave_domain = [
            ('employee_id', '=', user.employee_id.id),
            ('state', 'in', ('validate', 'validate1')),
            ('request_date_from', '<=', today),
            ('request_date_to', '>=', today),
        ]
        return bool(self.env['hr.leave'].search(leave_domain, limit=1))

    @api.model
    def _coerce_users(self, result):
        """Convert Python approver expression result into a res.users recordset."""
        users = self.env['res.users']
        if not result:
            return users
        if getattr(result, '_name', False) == 'res.users':
            return result
        if getattr(result, '_name', False) == 'hr.employee':
            return result.mapped('user_id')
        if isinstance(result, int):
            return users.browse(result)
        if isinstance(result, (list, tuple)):
            return users.browse([item.id if hasattr(item, 'id') else item for item in result])
        raise UserError(_('Python approver expression must return res.users, hr.employee, user id, or a list.'))

    @api.model
    def action_submit_record_for_manual_approval(self, record):
        """Public service for manual approval button integrations on target models."""
        requests = self._trigger_for_records(record, 'manual')
        if not requests:
            raise UserError(_('No manual approval rule matched this record.'))
        return requests

    @api.model
    def action_force_approve(self, request):
        """Force approve a request for authorized users."""
        if not self.env.user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_admin'):
            raise UserError(_('Only an authorized user can force approve a request.'))
        request.with_user(self.env.user).with_context(sh_skip_dynamic_approval=True)._force_approve_by_authorized_user(
            self.env.user
        )
        return True

    @api.model
    def action_manual_escalate(self, request):
        """Manually escalate a request for authorized users."""
        if not self.env.user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_admin'):
            raise UserError(_('Only an authorized user can manually escalate a request.'))
        request.with_user(self.env.user).with_context(sh_skip_dynamic_approval=True)._manual_escalate_by_authorized_user(
            self.env.user
        )
        return True
