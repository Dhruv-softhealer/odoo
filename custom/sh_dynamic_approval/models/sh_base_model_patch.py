# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import api, fields, models, _
from odoo.models import BaseModel
from odoo.exceptions import UserError


def _approval_engine_available(env):
    """Return whether the approval engine model is loaded in the current registry."""
    return 'sh.approval.engine' in env.registry.models


class BaseModelExtend(models.AbstractModel):
    _inherit = 'base'

    sh_is_under_approval = fields.Boolean(
        string='Is Under Approval',
        compute='_compute_sh_is_under_approval',
        search='_search_sh_is_under_approval'
    )
    sh_dynamic_approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled'),
    ], string='Dynamic Approval State', compute='_compute_sh_dynamic_approval_state', store=False, search='_search_sh_dynamic_approval_state')

    sh_can_cancel_approval = fields.Boolean(
        string='Can Cancel Approval',
        compute='_compute_sh_can_cancel_approval',
        search=False
    )

    def action_sh_send_for_manual_approval(self):
        """Manually trigger the dynamic approval process for this record."""
        self.ensure_one()
        if not _approval_engine_available(self.env):
            return True
            
        existing_request = self.env['sh.approval.request'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('state', '=', 'pending'),
        ])
        if existing_request:
            raise UserError(_('This record is already pending approval.'))
            
        approval_engine = self.env['sh.approval.engine']
        created_request = approval_engine._trigger_for_records(self, event='manual')
        if not created_request:
            raise UserError(_('No manual approval rules are configured or applicable for this record.'))
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Approval Requested'),
                'message': _('The manual approval request has been submitted successfully.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def _compute_sh_dynamic_approval_state(self):
        """Compute the overall approval state of the record."""
        if not _approval_engine_available(self.env):
            for record in self:
                record.sh_dynamic_approval_state = False
            return
            
        approval_engine = self.env['sh.approval.engine']
        if self._name in approval_engine._excluded_models():
            for record in self:
                record.sh_dynamic_approval_state = False
            return
            
        requests = self.env['sh.approval.request'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
        ], order='id desc')
        
        state_map = {}
        for req in requests:
            if req.res_id not in state_map:
                state_map[req.res_id] = req.state
                
        for record in self:
            record.sh_dynamic_approval_state = state_map.get(record.id, 'draft')

    def _compute_sh_is_under_approval(self):
        """Compute whether the record is currently under pending approval."""
        if not _approval_engine_available(self.env):
            for record in self:
                record.sh_is_under_approval = False
            return
            
        approval_engine = self.env['sh.approval.engine']
        if self._name in approval_engine._excluded_models():
            for record in self:
                record.sh_is_under_approval = False
            return

        # Fetch all pending requests for this model
        requests = self.env['sh.approval.request'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
            ('state', '=', 'pending')
        ])
        pending_ids = set(requests.mapped('res_id'))
        for record in self:
            record.sh_is_under_approval = record.id in pending_ids

    def _compute_sh_can_cancel_approval(self):
        """Compute if the current user can cancel the pending approval."""
        if not _approval_engine_available(self.env):
            for record in self:
                record.sh_can_cancel_approval = False
            return
            
        approval_engine = self.env['sh.approval.engine']
        if self._name in approval_engine._excluded_models():
            for record in self:
                record.sh_can_cancel_approval = False
            return

        is_admin = self.env.user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_admin')
        for record in self:
            request = self.env['sh.approval.request'].sudo().search([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id),
                ('state', '=', 'pending')
            ], limit=1)
            
            if request:
                record.sh_can_cancel_approval = is_admin or request.requester_id == self.env.user
            else:
                record.sh_can_cancel_approval = False

    def _search_sh_is_under_approval(self, operator, value):
        """Allow searching records that are under approval."""
        if not _approval_engine_available(self.env) or operator not in ('=', '!=') or not isinstance(value, bool):
            return []
            
        is_pending = value if operator == '=' else not value
        approval_engine = self.env['sh.approval.engine']
        if self._name in approval_engine._excluded_models():
            return []
            
        requests = self.env['sh.approval.request'].sudo().search([
            ('res_model', '=', self._name),
            ('state', '=', 'pending')
        ])
        pending_ids = list(set(requests.mapped('res_id')))
        
        if is_pending:
            return [('id', 'in', pending_ids)]
        else:
            return [('id', 'not in', pending_ids)]

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Dynamically inject an approval warning banner into form views."""
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        
        if view_type == 'form' and _approval_engine_available(self.env):
            approval_engine = self.env['sh.approval.engine']
            if self._name not in approval_engine._excluded_models():
                # Check if there are any active approval types for this model
                has_rules = self.env['sh.approval.type'].sudo().search_count([('model', '=', self._name)]) > 0
                if has_rules:
                    from lxml import etree
                    
                    is_string = isinstance(arch, str)
                    doc = etree.fromstring(arch) if is_string else arch
                    
                    # Ensure the fields are present so invisible condition works
                    field_node = etree.Element('field', name='sh_is_under_approval', invisible='1')
                    doc.insert(0, field_node)
                    can_cancel_field_node = etree.Element('field', name='sh_can_cancel_approval', invisible='1')
                    doc.insert(0, can_cancel_field_node)
                    
                    # Create the alert banner
                    alert_node = etree.Element('div', **{
                        'class': 'alert alert-warning text-center',
                        'role': 'alert',
                        'invisible': 'not sh_is_under_approval',
                        'style': 'margin-bottom: 0px; padding: 10px; font-weight: bold; border-radius: 0px;'
                    })
                    
                    icon_node = etree.Element('i', **{'class': 'fa fa-lock mr-2'})
                    alert_node.append(icon_node)
                    
                    span_node = etree.Element('span')
                    span_node.text = _(" This record is locked. It is currently pending approval and tracked fields cannot be modified.")
                    alert_node.append(span_node)
                    
                    # Ensure header exists
                    sheet = doc.find('.//sheet')
                    header = doc.find('.//header')
                    
                    if header is None:
                        header = etree.Element('header')
                        if sheet is not None:
                            sheet.addprevious(header)
                        else:
                            doc.insert(0, header)
                            
                    # Inject Cancel Request Button
                    cancel_btn_node = etree.Element('button', **{
                        'name': 'action_sh_cancel_dynamic_approval',
                        'type': 'object',
                        'string': _('Cancel Request'),
                        'class': 'btn-secondary',
                        'invisible': "not sh_can_cancel_approval"
                    })
                    header.insert(0, cancel_btn_node)
                    
                    # Inject Manual Approval UI
                    has_manual_rules = self.env['sh.approval.type'].sudo().search_count([('model', '=', self._name), ('trigger_event', '=', 'manual')]) > 0
                    if has_manual_rules:
                        state_field_node = etree.Element('field', name='sh_dynamic_approval_state', invisible='1')
                        doc.insert(0, state_field_node)
                        
                        btn_node = etree.Element('button', **{
                            'name': 'action_sh_send_for_manual_approval',
                            'type': 'object',
                            'string': _('Submit For Dynamic Approval'),
                            'class': 'btn-primary',
                            'invisible': "sh_dynamic_approval_state in ('pending', 'approved')"
                        })
                        header.insert(0, btn_node)
                        
                        statusbar_node = etree.Element('field', **{
                            'name': 'sh_dynamic_approval_state',
                            'widget': 'statusbar',
                            'statusbar_visible': 'draft,pending,approved,refused',
                        })
                        header.append(statusbar_node)
                    
                    # Insert warning banner
                    header.addnext(alert_node)

                    # Make all fields visually read-only when pending approval
                    for node in doc.xpath(".//field"):
                        field_name = node.get("name")
                        if field_name in ('sh_is_under_approval', 'sh_dynamic_approval_state'):
                            continue
                        existing_readonly = node.get("readonly")
                        if existing_readonly:
                            if existing_readonly not in ("1", "True", "true"):
                                node.set("readonly", f"({existing_readonly}) or sh_is_under_approval")
                        else:
                            node.set("readonly", "sh_is_under_approval")
                        
                    if is_string:
                        arch = etree.tostring(doc, encoding='unicode')
                    
        return arch, view

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not _approval_engine_available(self.env):
            return records
        # ``mail.activity`` subscribes its assignee to the target thread. At
        # this point an inherited model can still be completing its standard
        # create flow (``hr.employee`` creates its work contact afterwards).
        # Keep approval activities on their own request until that flow ends.
        self.env['sh.approval.engine'].with_context(
            sh_approval_target_create_in_progress=True,
        )._trigger_for_records(records, 'create')
        return records

    def action_sh_cancel_dynamic_approval(self):
        """Cancel the pending dynamic approval requests."""
        if not _approval_engine_available(self.env):
            return
            
        for record in self:
            requests = self.env['sh.approval.request'].sudo().search([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id),
                ('state', '=', 'pending')
            ])
            
            for request in requests:
                is_admin = self.env.user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_admin')
                if not is_admin and request.requester_id != self.env.user:
                    raise UserError(_('You are not authorized to cancel this approval request. Only the requester or an Administrator can cancel it.'))
                request.action_cancel()

    def write(self, vals):
        changed_fields = list(vals.keys())
        if not _approval_engine_available(self.env):
            return super().write(vals)
            
        if self.env.context.get('sh_skip_dynamic_approval'):
            return super().write(vals)
            
        approval_engine = self.env['sh.approval.engine']
        approval_engine._check_record_locked(self, changed_fields=changed_fields)
        
        # Stage writes for tracked fields and get mapping of staged fields per record
        staged_records, staged_fields_by_record = approval_engine._stage_write_for_approval(self, vals, changed_fields=changed_fields)
        records_to_write = self - staged_records
        
        result = True
        # For records that don't need staging, apply everything normally
        if records_to_write:
            result = super(BaseModelExtend, records_to_write).write(vals)
            approval_engine._trigger_for_records(records_to_write, 'write', changed_fields=changed_fields)
            
            # Auto-resubmit cancelled requests for records that successfully bypassed write staging
            for record in records_to_write:
                cancelled_reqs = self.env['sh.approval.request'].sudo().search([
                    ('res_model', '=', record._name),
                    ('res_id', '=', record.id),
                    ('state', '=', 'cancelled')
                ])
                for cancelled_req in cancelled_reqs:
                    cancelled_req.action_resubmit()
            
        # For staged records, only apply the UNTRACKED fields that were not staged
        if staged_records:
            for record in staged_records:
                staged_fields = staged_fields_by_record.get(record.id, [])
                untracked_vals = {k: v for k, v in vals.items() if k not in staged_fields}
                if untracked_vals:
                    super(BaseModelExtend, record).write(untracked_vals)

        # Cross-module synchronization: if record was natively approved/rejected, update pending requests
        if not self._context.get('sh_skip_activation_sync') and 'sh_activation_state' in vals:
            for record in self:
                requests = self.env['sh.approval.request'].sudo().search([
                    ('res_model', '=', record._name),
                    ('res_id', '=', record.id),
                    ('state', '=', 'pending')
                ])
                for req in requests:
                    if vals['sh_activation_state'] == 'approved':
                        req.with_context(sh_skip_activation_sync=True).sudo()._force_approve_by_authorized_user(self.env.user)
                    elif vals['sh_activation_state'] == 'rejected':
                        pending_line = req.line_ids.filtered(lambda l: l.state in ('pending', 'escalated')).sorted('sequence')[:1]
                        if pending_line:
                            from odoo import fields
                            req.sudo().write({'state': 'refused', 'last_refusal_reason': 'Rejected from target record', 'completed_date': fields.Datetime.now()})
                            pending_line.sudo().write({'state': 'refused', 'note': 'Rejected from target record', 'action_date': fields.Datetime.now()})
                    
        return result

    def unlink(self):
        if not _approval_engine_available(self.env):
            return super().unlink()
            
        approval_engine = self.env['sh.approval.engine']
        if not self.env.context.get('sh_skip_dynamic_approval') and self._name not in approval_engine._excluded_models():
            pending_requests = self.env['sh.approval.request'].sudo().search([
                ('res_model', '=', self._name),
                ('res_id', 'in', self.ids),
                ('state', '=', 'pending'),
            ], limit=1)
            if pending_requests:
                raise UserError(_('You cannot delete a record that is pending approval.'))
                
        return super().unlink()
