# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from datetime import timedelta
import base64
import hashlib
import hmac
import json
import pickle
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import consteq


class ShApprovalRequest(models.Model):
    """Runtime approval workflow instance linked to one target business record."""

    _name = 'sh.approval.request'
    _description = 'Dynamic Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submitted_date desc, id desc'

    name = fields.Char(required=True, default=lambda self: _('New Approval Request'), tracking=True)
    approval_type_id = fields.Many2one('sh.approval.type', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    model_id = fields.Many2one('ir.model', related='approval_type_id.model_id', store=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    record_ref = fields.Reference(selection='_selection_target_models', string='Record', compute='_compute_record_ref')
    record_name = fields.Char(compute='_compute_record_name', store=True)
    requester_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, index=True)
    submitted_date = fields.Datetime(default=fields.Datetime.now, index=True)
    completed_date = fields.Datetime()
    access_token = fields.Char(copy=False, index=True)
    current_level_id = fields.Many2one('sh.approval.level', compute='_compute_current_level', store=True)
    current_sequence = fields.Integer(compute='_compute_current_level', store=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('refused', 'Refused'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many('sh.approval.line', 'request_id', string='Approval Lines')
    log_ids = fields.One2many('sh.approval.log', 'request_id', string='Audit Trail')
    resubmission_count = fields.Integer(default=0)
    last_refusal_reason = fields.Text()
    previous_snapshot = fields.Text()
    modification_summary = fields.Text()
    trigger_event = fields.Selection(
        [
            ('create', 'On Creation'),
            ('write', 'On Updation'),
            ('manual', 'Manual Approval Button'),
        ],
        default='create',
        required=True,
        index=True,
    )
    staged_write_payload = fields.Binary(
        string='Staged Update Values',
        attachment=False,
        copy=False,
    )
    staged_write_summary = fields.Text(readonly=True)
    days_pending = fields.Integer(compute='_compute_days_pending')
    can_current_user_approve = fields.Boolean(compute='_compute_can_current_user_approve', search='_search_can_current_user_approve')

    @api.model
    def _selection_target_models(self):
        """Return installed non-transient models for reference display."""
        models_data = self.env['ir.model'].search([('transient', '=', False)], order='name')
        return [(model.model, model.name) for model in models_data]

    @api.depends('res_model', 'res_id')
    def _compute_record_ref(self):
        """Compute dynamic reference to the target record."""
        for request in self:
            request.record_ref = '%s,%s' % (request.res_model, request.res_id) if request.res_model and request.res_id else False

    @api.depends('res_model', 'res_id')
    def _compute_record_name(self):
        """Compute readable target record name."""
        for request in self:
            request.record_name = request._get_target_record().display_name if request._get_target_record().exists() else ''

    @api.depends('line_ids.state', 'line_ids.sequence')
    def _compute_current_level(self):
        """Compute first pending level as the current level."""
        for request in self:
            pending_line = request.sudo().line_ids.filtered(lambda line: line.state in ('pending', 'escalated'))[:1]
            request.current_level_id = pending_line.level_id if pending_line else False
            request.current_sequence = pending_line.sequence if pending_line else 0

    @api.depends('submitted_date', 'state')
    def _compute_days_pending(self):
        """Compute request age while it is pending."""
        now = fields.Datetime.now()
        for request in self:
            if request.submitted_date and request.state == 'pending':
                request.days_pending = (now - request.submitted_date).days
            else:
                request.days_pending = 0

    def _compute_can_current_user_approve(self):
        """Compute whether the current user may approve at least one pending line."""
        current_user = self.env.user
        for request in self:
            if not current_user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_approver') and not current_user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_authorized_user'):
                request.can_current_user_approve = False
                continue
            if not request.approval_type_id.allow_self_approval and request.requester_id == current_user:
                request.can_current_user_approve = False
                continue
            request.can_current_user_approve = any(
                current_user.id in line.approver_ids.ids or current_user.id == line.alternative_user_id.id
                for line in request.sudo().line_ids.filtered(lambda item: item.state in ('pending', 'escalated'))
            )

    def _search_can_current_user_approve(self, operator, value):
        """Allow filtering by can_current_user_approve in domains."""
        if operator != '=' or not value:
            raise NotImplementedError(_('Search on can_current_user_approve only supports "=" True'))
        
        current_user = self.env.user
        if not current_user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_approver') and not current_user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_authorized_user'):
            return [('id', '=', False)]
            
        matching_lines = self.env['sh.approval.line'].sudo().search([
            ('state', 'in', ('pending', 'escalated')),
            '|',
            ('approver_ids', 'in', current_user.ids),
            ('alternative_user_id', '=', current_user.id)
        ])
        
        if not matching_lines:
            return [('id', '=', False)]
            
        return [
            ('id', 'in', matching_lines.mapped('request_id.id')),
            '|',
            ('approval_type_id.allow_self_approval', '=', True),
            ('requester_id', '!=', current_user.id),
        ]

    def _get_target_record(self):
        """Return target business record with elevated access rights to prevent multi-company crashes."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return self.env[self._name].sudo()
        return self.env[self.res_model].sudo().browse(self.res_id)

    def write(self, vals):
        """Intercept state changes to automatically sync back to target models."""
        res = super().write(vals)
        if 'state' in vals:
            self.sudo()._sync_target_state()
        return res

    def copy(self, default=None):
        """Prevent manual duplication of approval requests."""
        raise UserError(_('Approval requests cannot be duplicated. They must be generated by the engine.'))

    def _sync_target_state(self):
        """Synchronize the approval request state back to the target model if it has standard state fields."""
        for request in self:
            target = request._get_target_record()
            if not target or not target.exists():
                continue
                
            vals = {}
            if request.state == 'pending':
                if hasattr(target, 'sh_activation_state'):
                    vals['sh_activation_state'] = 'to_approve'
                    vals['active'] = False
                elif hasattr(target, 'sh_state'):
                    vals['sh_state'] = 'pending_approval'
                elif hasattr(target, 'state'):
                    field = target._fields.get('state')
                    if field and field.type == 'selection' and 'pending' in dict(field.selection if isinstance(field.selection, list) else field.selection(target)):
                        vals['state'] = 'pending'
            elif request.state == 'approved':
                if hasattr(target, 'sh_activation_state'):
                    vals['sh_activation_state'] = 'approved'
                elif hasattr(target, 'sh_state'):
                    vals['sh_state'] = 'active'
                elif hasattr(target, 'state'):
                    field = target._fields.get('state')
                    if field and field.type == 'selection' and 'done' in dict(field.selection if isinstance(field.selection, list) else field.selection(target)):
                        vals['state'] = 'done'
            elif request.state == 'refused':
                if hasattr(target, 'sh_activation_state'):
                    vals['sh_activation_state'] = 'rejected'
                    vals['active'] = False
                elif hasattr(target, 'sh_state'):
                    vals['sh_state'] = 'rejected'
                elif hasattr(target, 'state'):
                    field = target._fields.get('state')
                    if field and field.type == 'selection' and 'cancel' in dict(field.selection if isinstance(field.selection, list) else field.selection(target)):
                        vals['state'] = 'cancel'
            elif request.state in ('draft', 'cancelled'):
                if hasattr(target, 'sh_activation_state'):
                    vals['sh_activation_state'] = 'draft'
                    vals['active'] = False
                elif hasattr(target, 'sh_state'):
                    vals['sh_state'] = 'draft'
                elif hasattr(target, 'state'):
                    field = target._fields.get('state')
                    if field and field.type == 'selection' and 'draft' in dict(field.selection if isinstance(field.selection, list) else field.selection(target)):
                        vals['state'] = 'draft'
                    
            if vals:
                # If activating, also set standard Odoo active boolean if it exists
                if (vals.get('sh_state') == 'active' or vals.get('sh_activation_state') == 'approved') and hasattr(target, 'active'):
                    vals['active'] = True
                
                # Write to target, skipping engine interception to prevent infinite loops
                target.with_context(sh_skip_dynamic_approval=True).write(vals)

    def _ensure_access_token(self):
        """Create a stable access token used in secure email action links."""
        for request in self:
            if not request.access_token:
                request.sudo().write({'access_token': uuid.uuid4().hex})
        return self.access_token

    def _make_action_token(self, action, user_id, access_token=None):
        """Return a signed action token bound to this request, user and action."""
        self.ensure_one()
        secret = self.env['ir.config_parameter'].sudo().get_param('database.secret')
        payload = (self.env.cr.dbname, access_token or self.access_token or '', self.id, int(user_id), action)
        return hmac.new(secret.encode('utf-8'), repr(payload).encode('utf-8'), hashlib.sha256).hexdigest()

    def _check_action_token(self, action, user_id, token):
        """Validate a signed email action token."""
        self.ensure_one()
        if not token or not user_id:
            return False
        expected = self._make_action_token(action, user_id, access_token=self.access_token)
        return consteq(expected, token)

    def _get_action_url(self, action, user=None):
        """Build a public approval URL for email templates."""
        self.ensure_one()
        user_id = self.env.context.get('sh_approval_recipient_user_id')
        user = user or (self.env['res.users'].browse(user_id) if user_id else self.env.user)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        token = self._make_action_token(action, user.id, access_token=self._ensure_access_token())
        return '%s/sh_dynamic_approval/request/%s/%s?uid=%s&token=%s' % (
            base_url,
            self.id,
            action,
            user.id,
            token,
        )

    def _serialize_snapshot(self):
        """Serialize simple stored fields for resubmission comparison."""
        self.ensure_one()
        target = self._get_target_record()
        if not target or not target.exists():
            return {}
        snapshot = {}
        for field_name, field in target._fields.items():
            if not field.store or field.compute:
                continue
            if field.type in ('char', 'text', 'html', 'selection', 'integer', 'float', 'boolean', 'date', 'datetime'):
                snapshot[field_name] = target.sudo()[field_name]
            elif field.type == 'many2one':
                snapshot[field_name] = target.sudo()[field_name].id or False
        return snapshot

    def _compute_modification_summary(self, previous_snapshot):
        """Compare a previous snapshot with the current target record."""
        self.ensure_one()
        current_snapshot = self._serialize_snapshot()
        changes = []
        for field_name, old_value in (previous_snapshot or {}).items():
            new_value = current_snapshot.get(field_name)
            if old_value != new_value:
                changes.append('%s: %s -> %s' % (field_name, old_value, new_value))
        return '\n'.join(changes)

    def _set_staged_write_values(self, vals):
        """Store proposed write values until the approval request is fully approved."""
        self.ensure_one()
        # Odoo write values may contain command objects, bytes, dates, or tuples; pickle preserves them for internal replay.
        payload = base64.b64encode(pickle.dumps(vals or {}, protocol=pickle.HIGHEST_PROTOCOL)).decode('ascii')
        self.write({
            'staged_write_payload': payload,
            'staged_write_summary': self._format_staged_write_summary(vals or {}),
        })

    def _get_staged_write_values(self):
        """Return stored write values for a staged update approval."""
        self.ensure_one()
        if not self.staged_write_payload:
            return {}
        payload = self.staged_write_payload
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        return pickle.loads(base64.b64decode(payload))

    def _format_staged_write_summary(self, vals):
        """Build a readable summary of proposed changed fields with old and new values."""
        self.ensure_one()
        target = self._get_target_record()
        labels = []
        for field_name, new_val in vals.items():
            field = target._fields.get(field_name) if target else False
            label = field.string if field else field_name
            
            if not target:
                labels.append('%s (%s): -> %s' % (label, field_name, new_val))
                continue
                
            old_val = getattr(target, field_name, False)
            old_display = str(old_val)
            new_display = str(new_val)
            
            if field:
                if field.type == 'many2one':
                    old_display = old_val.display_name if old_val else 'False'
                    if new_val:
                        new_record = self.env[field.comodel_name].sudo().browse(new_val)
                        new_display = new_record.display_name if new_record.exists() else str(new_val)
                    else:
                        new_display = 'False'
                elif field.type == 'selection':
                    # Use sudo() in case the selection requires access rights
                    selection_dict = dict(field.selection if isinstance(field.selection, list) else field.selection(target.sudo()))
                    old_display = selection_dict.get(old_val, str(old_val))
                    new_display = selection_dict.get(new_val, str(new_val))
                elif field.type in ('many2many', 'one2many'):
                    old_display = '%s records' % len(old_val) if old_val else '0 records'
                    new_display = 'Update Payload: %s' % str(new_val)
                elif field.type == 'binary':
                    old_display = 'Binary Data' if old_val else 'False'
                    new_display = 'Binary Data' if new_val else 'False'
                    
            labels.append('%s (%s): %s -> %s' % (label, field_name, old_display, new_display))
            
        return '\n'.join(labels)

    def _apply_staged_write_values(self):
        """Apply approved staged update values to the target record."""
        for request in self.filtered(lambda item: item.trigger_event == 'write' and item.staged_write_payload):
            target = self.env[request.res_model].with_user(request.requester_id).browse(request.res_id).exists()
            if not target:
                request._log_event('error', _('Approved staged update could not be applied because the record no longer exists.'))
                continue
            vals = request._get_staged_write_values()
            if vals:
                target.with_context(sh_skip_dynamic_approval=True).write(vals)
                request._log_event('approved', _('Approved staged update values were applied to the target record.'))

    def _notification_level_name(self):
        """Expose the acted-on level name to mail templates through the render context."""
        return self.env.context.get('sh_notification_level_name', '')

    def _notification_actor_name(self):
        """Expose the acting user's display name to mail templates through the render context."""
        return self.env.context.get('sh_notification_actor_name', '')

    def _notification_note(self):
        """Expose a notification note to mail templates through the render context."""
        return self.env.context.get('sh_notification_note', '')

    def _notification_modification_summary(self):
        """Expose the current modification summary to mail templates."""
        return self.modification_summary or ''

    def _approval_partners(self, include_requester=False, include_approvers=True, line_ids=None):
        """Return a consolidated list of partners involved in the request."""
        self.ensure_one()
        partners = self.env['res.partner'].sudo()
        if include_requester and self.requester_id:
            partners |= self.requester_id.sudo().partner_id
        if include_approvers:
            lines = line_ids if line_ids is not None else self.line_ids
            partners |= lines.mapped('approver_ids').sudo().mapped('partner_id')
            partners |= lines.mapped('alternative_user_id').sudo().mapped('partner_id')
            partners |= lines.mapped('action_user_id').sudo().mapped('partner_id')
        return partners

    def _log_event(self, action, note=False, actor=None, level=False):
        """Create an immutable approval audit log entry and notify target chatter."""
        for request in self:
            self.env['sh.approval.log'].sudo().create({
                'request_id': request.id,
                'company_id': request.company_id.id,
                'action': action,
                'actor_id': (actor or self.env.user).id,
                'level_id': level.id if level else False,
                'note': note or '',
            })
            
            target = request._get_target_record()
            if target and hasattr(target, 'message_post'):
                action_labels = {
                    'triggered': _('Approval Triggered'),
                    'submitted': _('Approval Request Submitted'),
                    'email_sent': _('Approval Notification Sent'),
                    'approved': _('Approved'),
                    'refused': _('Refused'),
                    'auto_approved': _('Auto-Approved'),
                    'escalated': _('Escalated'),
                    'completed': _('Approval Completed'),
                    'error': _('Approval Error'),
                }
                action_label = action_labels.get(action, action.title())
                msg = "%s: %s" % (_("Dynamic Approval"), action_label)
                if level:
                    msg += " | %s: %s" % (_("Level"), level.name)
                if note:
                    msg += " | %s" % note
                
                actor_user = actor or self.env.user
                try:
                    author_id = actor_user.sudo().partner_id.id if actor_user else self.env.user.sudo().partner_id.id
                except Exception:
                    author_id = self.env.user.sudo().partner_id.id
                
                notify_partners = self.env['res.partner']
                if action in ('submitted', 'email_sent', 'escalated'):
                    if level:
                        level_lines = request.line_ids.filtered(lambda l: l.level_id == level)
                        notify_partners |= request._approval_partners(include_approvers=True, line_ids=level_lines)
                elif action in ('approved', 'refused', 'completed', 'error', 'auto_approved'):
                    notify_partners |= request._approval_partners(include_requester=True)
                
                target.sudo().with_context(mail_post_autofollow=False, mail_create_nosubscribe=True).message_post(
                    body=msg, 
                    author_id=author_id,
                    subtype_xmlid='mail.mt_note',
                    message_type='notification',
                )

    def action_submit(self):
        """Submit a draft or refused request into pending approval."""
        for request in self:
            if request.state not in ('draft', 'refused'):
                raise UserError(_('Only draft or refused requests can be submitted.'))
            if not request.line_ids:
                self.env['sh.approval.engine']._prepare_request_lines(request)
            request._ensure_access_token()
            notification_event = self.env.context.get('sh_submit_notification_event', 'request')
            values = {
                'state': 'pending',
                'submitted_date': fields.Datetime.now(),
                'previous_snapshot': json.dumps(request._serialize_snapshot(), default=str),
            }
            if not self.env.context.get('sh_keep_modification_summary'):
                values['modification_summary'] = False
            request.sudo().write(values)
            request.sudo().line_ids.filtered(lambda l: l.state == 'draft').write({'state': 'pending'})
            request._activate_current_level()
            request._log_event('submitted', _('Approval request submitted.'))
            request._notify_pending_lines(template_event=notification_event)

    def _activate_current_level(self):
        """Set the activation date for the currently active pending level."""
        for request in self:
            first_pending = request.sudo().line_ids.filtered(lambda line: line.state == 'pending').sorted('sequence')
            if first_pending and not first_pending[0].activation_date:
                first_pending[0].sudo().write({'activation_date': fields.Datetime.now()})

    def action_approve(self):
        """Approve pending approval lines assigned to the current user."""
        for request in self:
            request._approve_by_user(self.env.user)

    def action_bulk_approve(self):
        """Approve all selected requests where current user is authorized."""
        approved_count = 0
        skipped_count = 0
        for request in self:
            try:
                request._approve_by_user(self.env.user)
                approved_count += 1
            except UserError:
                skipped_count += 1
        message = _('Approved: %(approved)s | Skipped: %(skipped)s') % {
            'approved': approved_count,
            'skipped': skipped_count,
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Approval'), 
                'message': message, 
                'type': 'success', 
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def _approve_by_user(self, user):
        """Approve the highest pending line assigned to user and auto-approve lower pending lines."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('Only pending approval requests can be approved.'))
        if not user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_approver') and not user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_authorized_user'):
            raise UserError(_('You do not have the necessary access rights (Approver) to approve this request.'))
        if not self.approval_type_id.allow_self_approval and self.requester_id == user:
            raise UserError(_('You cannot approve your own request. Self-approval is disabled for this type.'))
        user_pending_lines = self.sudo().line_ids.filtered(
            lambda line: line.state in ('pending', 'escalated') and (user in line.approver_ids or user == line.alternative_user_id)
        ).sorted('sequence', reverse=True)
        
        if not user_pending_lines:
            raise UserError(_('You are not allowed to approve this request at its current level.'))

        active_line = user_pending_lines[0]
        refused_lower = self.sudo().line_ids.filtered(
            lambda line: line.sequence < active_line.sequence and line.state == 'refused'
        )
        if refused_lower:
            raise UserError(_('A lower approval level was already refused and cannot be superseded.'))

        lower_pending_lines = self.sudo().line_ids.filtered(
            lambda line: line.sequence < active_line.sequence and line.state in ('pending', 'escalated')
        )
        for lower_line in lower_pending_lines:
            lower_line.sudo().write({
                'state': 'auto_approved',
                'action_user_id': user.id,
                'action_date': fields.Datetime.now(),
                'note': _('Auto-approved: superseded by %(level)s approval by %(user)s.') % {
                    'level': active_line.level_id.name,
                    'user': user.display_name,
                },
            })
            self._log_event('auto_approved', lower_line.note, actor=user, level=lower_line.level_id)
            self._notify_auto_approval(lower_line, user)

        active_line.sudo().write({
            'state': 'approved',
            'action_user_id': user.id,
            'action_date': fields.Datetime.now(),
        })
        self.activity_unlink(['mail.mail_activity_data_todo'])
        self._activate_current_level()
        approval_note = _('Approved by %s.') % user.display_name
        if user == active_line.alternative_user_id:
            approval_note = _('Approved via delegated approver %s.') % user.display_name
        self._log_event('approved', approval_note, actor=user, level=active_line.level_id)

        if not self.sudo().line_ids.filtered(lambda line: line.state in ('pending', 'escalated', 'refused')):
            self._apply_staged_write_values()
            self.sudo().write({'state': 'approved', 'completed_date': fields.Datetime.now()})
            self._log_event('completed', _('Approval completed.'), actor=user)
            self._notify_template_for_partners(
                self._get_email_template('completed'),
                self._approval_partners(include_requester=True, include_approvers=True),
                line=active_line,
                action='view',
            )
            target_record = self._get_target_record()
            if hasattr(target_record, 'action_approve_activation'):
                target_record.with_context(sh_skip_activation_sync=True).sudo().action_approve_activation()
        else:
            self._notify_current_level()

    def _force_approve_by_authorized_user(self, user):
        """Force approve a request and mark all remaining pending lines as approved."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('Only pending approval requests can be force approved.'))
        if not self.env.user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_authorized_user'):
            raise UserError(_('Only an authorized user can force approve a request.'))

        for line in self.sudo().line_ids.filtered(lambda item: item.state in ('pending', 'escalated')):
            line.sudo().write({
                'state': 'approved',
                'action_user_id': user.id,
                'action_date': fields.Datetime.now(),
                'note': _('Force approved by authorized user %s.') % user.display_name,
            })
            self._log_event('approved', _('Force approved by authorized user %s.') % user.display_name, actor=user, level=line.level_id)

        self.activity_unlink(['mail.mail_activity_data_todo'])
        self._activate_current_level()
        self._apply_staged_write_values()
        self.sudo().write({'state': 'approved', 'completed_date': fields.Datetime.now()})
        self._log_event('completed', _('Force approval completed by authorized user %s.') % user.display_name, actor=user)
        self._notify_template_for_partners(
            self._get_email_template('completed'),
            self._approval_partners(include_requester=True, include_approvers=True),
            line=self.current_level_id and self.sudo().line_ids.filtered(lambda line: line.level_id == self.current_level_id)[:1],
            action='view',
        )
        target_record = self._get_target_record()
        if hasattr(target_record, 'action_approve_activation'):
            target_record.with_context(sh_skip_activation_sync=True).sudo().action_approve_activation()

    def action_open_refuse_wizard(self):
        """Open a refusal reason wizard for one or more selected approval requests."""
        view_id = self.env.ref('sh_dynamic_approval.view_sh_approval_refuse_wizard_form').id
        return {
            'name': _('Refuse Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'sh.approval.refuse.wizard',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_request_ids': [(6, 0, self.ids)],
            },
        }

    def _refuse_by_user(self, user, reason):
        """Refuse one pending approval line and stop the workflow."""
        self.ensure_one()
        if not reason:
            raise UserError(_('Refusal reason is required.'))
        if not self.approval_type_id.allow_self_approval and self.requester_id == user:
            raise UserError(_('You cannot refuse your own request. Self-approval is disabled for this type.'))

        first_pending = self.line_ids.filtered(lambda line: line.state in ('pending', 'escalated')).sorted('sequence')[:1]
        if not first_pending:
            raise UserError(_('No pending approval lines found.'))

        if user not in first_pending.approver_ids and user != first_pending.alternative_user_id:
            raise UserError(_('You are not allowed to refuse this request at its current level.'))
            
        eligible_line = first_pending
        eligible_line.sudo().write({
            'state': 'refused',
            'action_user_id': user.id,
            'action_date': fields.Datetime.now(),
            'note': reason if user != eligible_line.alternative_user_id else _('%(reason)s (Delegated approver)') % {
                'reason': reason,
            },
        })
        self.activity_unlink(['mail.mail_activity_data_todo'])
        self.sudo().write({'state': 'refused', 'last_refusal_reason': reason, 'completed_date': fields.Datetime.now()})
        refusal_note = reason
        if user == eligible_line.alternative_user_id:
            refusal_note = _('%(reason)s | Delegated action by %(user)s') % {
                'reason': reason,
                'user': user.display_name,
            }
        self._log_event('refused', refusal_note, actor=user, level=eligible_line.level_id)
        self._notify_template_for_partners(
            self._get_email_template('refused'),
            self._approval_partners(include_requester=True, include_approvers=True, line_ids=eligible_line),
            line=eligible_line,
            action='view',
        )
        target_record = self._get_target_record()
        if hasattr(target_record, 'action_reject_activation'):
            target_record.with_context(sh_skip_activation_sync=True).sudo().action_reject_activation()

    def action_modify(self):
        """Allow requester to correct a refused request and return to draft."""
        for request in self:
            if request.state != 'refused':
                raise UserError(_('Only refused requests can be modified.'))
            if request.requester_id != self.env.user and not self.env.user.has_group(
                'sh_dynamic_approval.group_sh_dynamic_approval_authorized_user'
            ):
                raise UserError(_('Only the requester or an authorized user can modify this request.'))
            request.sudo().write({'state': 'draft'})
            request.sudo().line_ids.write({'state': 'draft'})
            request._log_event('modified', _('Request reopened for modification.'))

    def action_resubmit(self):
        """Reset existing lines and resubmit the request after modification."""
        for request in self:
            if request.state != 'draft':
                raise UserError(_('Only draft requests can be resubmitted.'))
            previous_snapshot = json.loads(request.previous_snapshot or '{}')
            summary = request._compute_modification_summary(previous_snapshot)
            applicable_type = self.env['sh.approval.engine']._find_applicable_approval_type(request._get_target_record())
            type_changed = False
            if applicable_type and applicable_type != request.approval_type_id:
                request.sudo().write({'approval_type_id': applicable_type.id})
                type_changed = True
            if type_changed or request.approval_type_id.resubmission_mode == 'all':
                request.line_ids.sudo().unlink()
            else:
                request.sudo().line_ids.filtered(lambda line: line.state not in ('approved', 'auto_approved')).sudo().write({
                    'state': 'pending',
                    'action_user_id': False,
                    'action_date': False,
                    'notification_date': False,
                    'escalation_date': False,
                    'note': False,
                    'activation_date': False,
                })
            request.sudo().write({'resubmission_count': request.resubmission_count + 1})
            request.sudo().write({
                'modification_summary': summary,
                'previous_snapshot': json.dumps(request._serialize_snapshot(), default=str),
            })
            request._log_event('resubmitted', summary or _('Request resubmitted after modification.'))
            if not request.line_ids:
                self.env['sh.approval.engine']._prepare_request_lines(request)
            else:
                request.sudo().line_ids.filtered(lambda line: line.state in ('pending', 'escalated')).sudo().write({
                    'notification_date': False,
                })
            request.with_context(
                sh_keep_modification_summary=True,
                sh_submit_notification_event='resubmission',
            ).action_submit()

    def action_cancel(self):
        for request in self:
            if request.state not in ('pending', 'draft'):
                raise UserError(_('Only pending or draft requests can be cancelled.'))
            target = request._get_target_record()
            record_to_activity = target if target and hasattr(target, 'activity_unlink') else request
            record_to_activity.activity_unlink(['mail.mail_activity_data_todo'])
            request.sudo().line_ids.filtered(lambda item: item.state in ('pending', 'escalated')).sudo().write({'state': 'cancelled'})
            request.sudo().write({'state': 'cancelled', 'completed_date': fields.Datetime.now()})
            request._log_event('cancelled', _('Approval request cancelled.'))

    def action_force_approve(self):
        """UI wrapper that lets authorized users force approve a request."""
        for request in self:
            self.env['sh.approval.engine'].action_force_approve(request)

    def action_manual_escalate(self):
        """UI wrapper that lets authorized users manually escalate a request."""
        for request in self:
            self.env['sh.approval.engine'].action_manual_escalate(request)

    def action_open_record(self):
        """Open target business record."""
        self.ensure_one()
        return {
            'name': self.record_name,
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _manual_escalate_by_authorized_user(self, user):
        """Manually escalate the first pending line for authorized intervention."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('Only pending requests can be escalated.'))
        line = self.line_ids.filtered(lambda item: item.state in ('pending', 'escalated'))[:1]
        if not line:
            raise UserError(_('No pending approval line is available for escalation.'))
        line.write({
            'state': 'escalated',
            'escalation_date': fields.Datetime.now(),
            'note': _('Manually escalated by authorized user %s.') % user.display_name,
        })
        self._log_event('escalated', _('Manually escalated by authorized user %s.') % user.display_name, actor=user, level=line.level_id)
        self._notify_template_for_partners(
            self._get_email_template('escalated'),
            self._escalation_partners(line),
            line=line,
            action='view',
        )
        target = self._get_target_record()
        record_to_activity = target if target and hasattr(target, 'activity_unlink') else self
        record_to_activity.activity_unlink(['mail.mail_activity_data_todo'])
        if line.alternative_user_id:
            record_to_activity.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=line.alternative_user_id.id,
                summary=_('Escalated Approval Required: %s') % self.record_name,
                note=_('This request has been manually escalated to you (Level: %s).') % line.level_id.name,
            )

    def _notify_current_level(self):
        """Send approval request email to the current active pending line."""
        self._notify_pending_lines()

    def _notify_pending_lines(self, template_event='request'):
        """Send approval request emails to all active pending lines."""
        for request in self:
            pending_lines = request.sudo().line_ids.filtered(lambda item: item.state in ('pending', 'escalated')).sorted('sequence')
            for pending_line in pending_lines:
                if pending_line and not pending_line.notification_date:
                    partners = pending_line._notification_partner_ids()
                    if not partners:
                        continue
                    pending_line.sudo().write({'notification_date': fields.Datetime.now()})
                    request._notify_template_for_partners(
                        request._get_email_template(template_event),
                        partners,
                        line=pending_line,
                        action='view',
                    )
                
                # Schedule native Odoo To-Do activities for the approvers
                for partner in partners:
                    user = partner.user_ids[:1]
                    if user:
                        target = request._get_target_record()
                        record_to_activity = target if target and hasattr(target, 'activity_schedule') else request
                        record_to_activity.activity_schedule(
                            'mail.mail_activity_data_todo',
                            user_id=user.id,
                            summary=_('Approval Required: %s') % request.record_name,
                            note=_('You have a pending approval request (Level: %s).') % pending_line.level_id.name,
                        )
                        
                request._log_event('email_sent', _('Approval request email and activity sent.'), level=pending_line.level_id)

    def _get_template_record(self, template_or_xmlid, fallback_xmlid=None):
        """Resolve either a mail.template record or fallback XML id."""
        template = template_or_xmlid if getattr(template_or_xmlid, '_name', False) == 'mail.template' else False
        if template:
            return template
        xmlid = template_or_xmlid if isinstance(template_or_xmlid, str) else fallback_xmlid
        return self.env.ref(xmlid, raise_if_not_found=False) if xmlid else False

    def _notify_template(self, template_or_xmlid, email_values=None):
        """Send a configured mail template for each request."""
        for request in self:
            template = request._get_template_record(template_or_xmlid)
            if not template:
                continue
            template.send_mail(request.id, force_send=False, email_values=email_values)

    def _notify_template_for_partners(self, template_or_xmlid, partners, line=None, action='view'):
        """Render and send approval notification to specific partners."""
        self.ensure_one()
        template = template_or_xmlid if isinstance(template_or_xmlid, models.Model) else self.env.ref(
            template_or_xmlid, raise_if_not_found=False
        )
        if not template or not partners:
            return

        partners = partners.sudo()
        for partner in partners:
            user = partner.user_ids[:1]
            if not user:
                continue
            context_vals = {
                'sh_approval_recipient_user_id': user.id,
                'sh_notification_level_name': line.level_id.name if line else '',
                'sh_notification_line_id': line.id if line else False,
            }
            template.with_context(**context_vals).send_mail(
                self.id,
                force_send=False,
                email_values={
                    'recipient_ids': [(6, 0, [partner.id])],
                    'email_to': partner.email,
                    'res_id': 0,
                    'model': False,
                },
            )
            
            # Send real-time bus notification (toast popup)
            if hasattr(self.env['bus.bus'], '_sendone'):
                subject = template.with_context(**context_vals)._render_field('subject', self.ids)[self.id]
                self.env['bus.bus'].sudo()._sendone(
                    partner,
                    'simple_notification',
                    {
                        'title': _('Approval Notification'),
                        'message': subject,
                        'sticky': False,
                        'type': 'info',
                    }
                )

    def _notify_auto_approval(self, line, actor):
        """Notify the requester when a lower level is auto-approved."""
        self.ensure_one()
        template = self._get_email_template('auto_approved')
        if not template or not self.requester_id.sudo().partner_id:
            return
        
        context_vals = {
            'sh_notification_level_name': line.level_id.name,
            'sh_notification_actor_name': actor.display_name,
            'sh_notification_note': line.note or '',
        }
        template.with_context(**context_vals).send_mail(
            self.id,
            force_send=False,
            email_values={
                'recipient_ids': [(6, 0, [self.requester_id.sudo().partner_id.id])],
                'email_to': self.requester_id.sudo().partner_id.email,
            },
        )
        
        # Send real-time bus notification (toast popup)
        if hasattr(self.env['bus.bus'], '_sendone'):
            subject = template.with_context(**context_vals)._render_field('subject', self.ids)[self.id]
            self.env['bus.bus'].sudo()._sendone(
                self.requester_id.sudo().partner_id,
                'simple_notification',
                {
                    'title': _('Approval Notification'),
                    'message': subject,
                    'sticky': False,
                    'type': 'info',
                }
            )

    def _escalation_partners(self, line):
        """Return partners that should receive escalation notifications."""
        self.ensure_one()
        partners = self.env['res.partner'].sudo()
        if line.alternative_user_id:
            partners |= line.alternative_user_id.sudo().partner_id
        return partners
        
    def _intervention_partners(self):
        """Return admin and authorized user partners for critical interventions."""
        partners = self.env['res.partner'].sudo()
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin_user:
            partners |= admin_user.sudo().partner_id
        authorized_group = self.env.ref(
            'sh_dynamic_approval.group_sh_dynamic_approval_authorized_user',
            raise_if_not_found=False,
        )
        if authorized_group:
            group_users = getattr(authorized_group, 'all_user_ids', False) or getattr(authorized_group, 'user_ids', False)
            partners |= group_users.sudo().mapped('partner_id')
        return partners

    def _notify_escalation_intervention(self, line):
        """Notify admins or authorized users when no alternative approver exists."""
        self.ensure_one()
        partners = self._intervention_partners()
        if not partners:
            return
        self._notify_template_for_partners(
            self._get_email_template('escalated'),
            partners,
            line=line,
            action='view',
        )

    def _process_escalation_line(self, line):
        """Escalate one overdue approval line and send the correct notification."""
        self.ensure_one()
        line.write({'state': 'escalated', 'escalation_date': fields.Datetime.now()})
        note = _('Escalated to alternative approver %s.') % line.alternative_user_id.display_name if line.alternative_user_id else _(
            'Escalated for admin intervention.'
        )
        self._log_event('escalated', note, actor=self.env.user, level=line.level_id)
        if line.alternative_user_id:
            self._notify_template_for_partners(
                self._get_email_template('escalated'),
                self._escalation_partners(line),
                line=line,
                action='view',
            )
            self.activity_unlink(['mail.mail_activity_data_todo'])
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=line.alternative_user_id.id,
                summary=_('Escalated Approval Required: %s') % self.record_name,
                note=_('This request has timed out and escalated to you (Level: %s).') % line.level_id.name,
            )
        else:
            self._notify_escalation_intervention(line)
        return line

    def _get_email_template(self, event):
        """Return the configured template for an event with fallback defaults."""
        self.ensure_one()
        mapping = {
            'request': (self.approval_type_id.request_template_id, 'sh_dynamic_approval.mail_template_sh_approval_request_created'),
            'auto_approved': (
                self.approval_type_id.auto_approved_template_id,
                'sh_dynamic_approval.mail_template_sh_approval_auto_approved',
            ),
            'completed': (self.approval_type_id.completed_template_id, 'sh_dynamic_approval.mail_template_sh_approval_completed'),
            'refused': (self.approval_type_id.refused_template_id, 'sh_dynamic_approval.mail_template_sh_approval_refused'),
            'escalated': (self.approval_type_id.escalated_template_id, 'sh_dynamic_approval.mail_template_sh_approval_escalated'),
            'resubmission': (
                self.approval_type_id.resubmission_template_id,
                'sh_dynamic_approval.mail_template_sh_approval_resubmission',
            ),
        }
        template, fallback_xmlid = mapping[event]
        return template or self.env.ref(fallback_xmlid, raise_if_not_found=False)

    @api.model
    def _cron_escalate_pending_approvals(self, batch_size=200):
        """Escalate overdue approval lines in batches with per-batch commits."""
        line_model = self.env['sh.approval.line']
        base_domain = [('state', '=', 'pending'), ('level_id.escalation_timeout', '>', 0), ('activation_date', '!=', False)]
        last_id = 0
        while True:
            pending_lines = line_model.search(base_domain + [('id', '>', last_id)], limit=batch_size, order='id')
            if not pending_lines:
                break
            for line in pending_lines:
                last_id = line.id
                try:
                    deadline = line.activation_date + timedelta(hours=line.level_id.escalation_timeout)
                    if fields.Datetime.now() >= deadline:
                        line.request_id._process_escalation_line(line)
                except Exception as error:
                    line.request_id._log_event('error', _('Escalation failed: %s') % error, level=line.level_id)
            self.env.cr.commit()


class ShApprovalLine(models.Model):
    """Approval line assigned to one workflow level."""

    _name = 'sh.approval.line'
    _description = 'Dynamic Approval Line'
    _order = 'sequence, id'

    request_id = fields.Many2one('sh.approval.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    level_id = fields.Many2one('sh.approval.level', required=True, ondelete='restrict', index=True)
    sequence = fields.Integer(required=True, default=10, index=True)
    approver_ids = fields.Many2many(
        'res.users',
        'sh_approval_line_user_rel',
        'line_id',
        'user_id',
        string='Approvers (Internal)',
    )
    approver_display = fields.Char(
        string='Approvers',
        compute='_compute_approver_display',
    )
    alternative_user_id = fields.Many2one('res.users', string='Alternative Approver', check_company=False)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('auto_approved', 'Auto-Approved'),
            ('refused', 'Refused'),
            ('escalated', 'Escalated'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        required=True,
        index=True,
    )
    action_user_id = fields.Many2one('res.users', string='Action By')
    action_date = fields.Datetime()
    activation_date = fields.Datetime()
    notification_date = fields.Datetime()
    escalation_date = fields.Datetime()
    note = fields.Text()

    def _notification_partner_ids(self):
        """Return partners that should receive current level emails."""
        self.ensure_one()
        users = self.approver_ids
        if self.state == 'escalated' and self.alternative_user_id:
            users |= self.alternative_user_id
        return users.sudo().mapped('partner_id')

    @api.depends('level_id.approval_method', 'level_id.group_id.name', 'level_id.job_id.name', 'approver_ids.name')
    def _compute_approver_display(self):
        for line in self:
            if line.level_id.approval_method == 'group' and line.level_id.group_id:
                line.approver_display = line.level_id.group_id.name
            elif line.level_id.approval_method == 'job' and line.level_id.job_id:
                line.approver_display = line.level_id.job_id.name
            else:
                line.approver_display = ', '.join(line.approver_ids.sudo().mapped('name'))


class ShApprovalLog(models.Model):
    """Immutable audit log for approval workflow events."""

    _name = 'sh.approval.log'
    _description = 'Dynamic Approval Audit Log'
    _order = 'create_date desc, id desc'

    request_id = fields.Many2one('sh.approval.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    action = fields.Selection(
        [
            ('triggered', 'Approval Triggered'),
            ('submitted', 'Submitted'),
            ('email_sent', 'Email Sent'),
            ('approved', 'Approved'),
            ('auto_approved', 'Auto-Approved'),
            ('refused', 'Refused'),
            ('modified', 'Modified'),
            ('resubmitted', 'Resubmitted'),
            ('escalated', 'Escalated'),
            ('cancelled', 'Cancelled'),
            ('completed', 'Approval Complete'),
            ('error', 'Error'),
        ],
        required=True,
        index=True,
    )
    actor_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    level_id = fields.Many2one('sh.approval.level')
    note = fields.Text()


class ShApprovalRefuseWizard(models.TransientModel):
    """Collect a mandatory refusal reason before refusing approval requests."""

    _name = 'sh.approval.refuse.wizard'
    _description = 'Dynamic Approval Refusal Wizard'
    
    is_from_email = fields.Boolean(default=False)

    request_ids = fields.Many2many(
        'sh.approval.request',
        string='Approval Requests',
        required=True,
        default=lambda self: self.env.context.get('active_ids', [])
    )
    reason = fields.Text(required=True)

    def action_confirm_refuse(self):
        """Refuse selected approval requests with the provided reason."""
        self.ensure_one()
        for approval_request in self.request_ids:
            approval_request._refuse_by_user(self.env.user, self.reason)
        return self._return_to_request()

    def action_cancel(self):
        """Cancel the wizard."""
        return self._return_to_request()

    def _return_to_request(self):
        """Return to the form view if opened from email, else close the wizard."""
        self.ensure_one()
        if len(self.request_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sh.approval.request',
                'res_id': self.request_ids[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}
