# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval


class ShApprovalType(models.Model):
    """Configuration record that defines one approval workflow for one Odoo model."""

    _name = 'sh.approval.type'
    _description = 'Dynamic Approval Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Odoo Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
        tracking=True,
    )
    model = fields.Char(related='model_id.model', store=True, index=True)
    trigger_event = fields.Selection(
        [
            ('create', 'On Creation'),
            ('write', 'On Updation'),
            ('both', 'On Creation and Updation'),
            ('manual', 'Manual Approval Button'),
        ],
        required=True,
        default='create',
        tracking=True,
    )
    allow_self_approval = fields.Boolean(
        string='Allow Self Approval',
        default=False,
        tracking=True,
        help='If disabled, the requester cannot approve their own request, even if they are in the approver group.',
    )
    resubmission_mode = fields.Selection(
        [
            ('all', 'Restart All Levels'),
            ('pending', 'Restart Pending Levels Only'),
        ],
        string='Resubmission Mode',
        default='all',
        tracking=True,
        help='Controls whether resubmission rebuilds all levels or only levels that were still pending.',
    )
    domain_filter = fields.Char(
        default='[]',
        help='Standard Odoo domain expression. Leave empty or use [] to apply to all records.',
    )
    update_field_ids = fields.Many2many(
        'ir.model.fields',
        'sh_approval_type_field_rel',
        'approval_type_id',
        'field_id',
        string='Tracked Update Fields',
        domain="[('model_id', '=', model_id), ('store', '=', True)]",
        help='When update trigger is enabled, approval starts only if one of these fields changes.',
    )
    level_ids = fields.One2many('sh.approval.level', 'approval_type_id', string='Approval Levels', copy=True)
    request_template_id = fields.Many2one('mail.template', string='Request Email Template')
    auto_approved_template_id = fields.Many2one('mail.template', string='Auto-Approved Email Template')
    completed_template_id = fields.Many2one('mail.template', string='Completed Email Template')
    refused_template_id = fields.Many2one('mail.template', string='Refused Email Template')
    escalated_template_id = fields.Many2one('mail.template', string='Escalated Email Template')
    resubmission_template_id = fields.Many2one('mail.template', string='Resubmission Email Template')
    request_count = fields.Integer(compute='_compute_request_count')

    @api.constrains('name', 'company_id')
    def _check_name_company_unique(self):
        """Approval Type name must be unique per company."""
        for approval_type in self:
            if self.search_count([
                ('name', '=', approval_type.name),
                ('company_id', '=', approval_type.company_id.id),
                ('id', '!=', approval_type.id)
            ]):
                raise ValidationError(_('Approval Type name must be unique per company.'))

    @api.depends('model_id')
    def _compute_request_count(self):
        """Compute linked approval request count for smart button display."""
        grouped_data = self.env['sh.approval.request'].read_group(
            [('approval_type_id', 'in', self.ids)],
            ['approval_type_id'],
            ['approval_type_id'],
        )
        mapped_count = {data['approval_type_id'][0]: data['approval_type_id_count'] for data in grouped_data}
        for approval_type in self:
            approval_type.request_count = mapped_count.get(approval_type.id, 0)


    @api.constrains('domain_filter')
    def _check_domain_filter(self):
        """Validate configured domain syntax during configuration save."""
        for approval_type in self:
            domain_text = approval_type.domain_filter or '[]'
            try:
                domain = Domain(safe_eval(domain_text, {'uid': self.env.uid}))
                if approval_type.model_id:
                    domain.validate(self.env[approval_type.model])
            except Exception as error:
                raise ValidationError(_('Invalid domain filter: %s') % error) from error

    @api.constrains('trigger_event', 'update_field_ids')
    def _check_update_fields(self):
        """Require explicit update fields for write based approvals."""
        for approval_type in self:
            if approval_type.trigger_event in ('write', 'both') and not approval_type.update_field_ids:
                raise ValidationError(_('Please select tracked update fields for update approval triggers.'))

    @api.constrains('level_ids')
    def _check_level_ids(self):
        """Ensure each approval type has at least one approval level."""
        for approval_type in self:
            if not approval_type.level_ids:
                raise ValidationError(_('At least one approval level is required.'))

    def action_view_requests(self):
        """Open approval requests created from this approval type."""
        self.ensure_one()
        return {
            'name': _('Approval Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'sh.approval.request',
            'view_mode': 'list,form',
            'domain': [('approval_type_id', '=', self.id)],
            'context': {'create': False, 'default_approval_type_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Create approval types and auto-create manual server actions when needed."""
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        for record in records:
            if not record.level_ids:
                raise ValidationError(_('At least one approval level is required.'))
        records._sync_manual_server_action()
        return records

    def write(self, vals):
        """Update approval types and keep manual server actions in sync."""
        result = super().write(vals)
        if 'model_id' in vals or 'active' in vals:
            self.env.registry.clear_cache()
        for record in self:
            if not record.level_ids:
                raise ValidationError(_('At least one approval level is required.'))
        self._sync_manual_server_action()
        return result

    def unlink(self):
        """Remove manual server actions when approval types are deleted."""
        self._remove_manual_server_action()
        self._remove_history_server_action()
        self.env.registry.clear_cache()
        return super().unlink()

    def _manual_action_xmlid(self):
        """Build a stable XML ID for the auto-generated manual action."""
        self.ensure_one()
        return 'sh_dynamic_approval.action_server_manual_%s' % self.id

    def _sync_manual_server_action(self):
        """Create or remove bound server actions for manual submission and approval history."""
        self._sync_history_server_action()
        manual_types = self.filtered(lambda record: record.trigger_event == 'manual')
        other_types = self - manual_types
        for approval_type in manual_types:
            action_name = '%s - Manual Submit for Approval' % approval_type.name
            action = self.env['ir.actions.server'].sudo().search([
                ('name', '=', action_name),
                ('model_id', '=', approval_type.model_id.id),
            ], limit=1)
            code = (
                "if records:\n"
                "    env['sh.approval.engine'].action_submit_record_for_manual_approval(records)\n"
                "    action = {'type': 'ir.actions.client', 'tag': 'reload'}\n"
            )
            action_vals = {
                'name': action_name,
                'model_id': approval_type.model_id.id,
                'binding_model_id': approval_type.model_id.id,
                'binding_type': 'action',
                'binding_view_types': 'form',
                'state': 'code',
                'code': code,
            }
            if action:
                action.write(action_vals)
            else:
                self.env['ir.actions.server'].sudo().create(action_vals)
        if other_types:
            other_types._remove_manual_server_action()

    def _sync_history_server_action(self):
        """Create a bound action that opens approval history from configured target records."""
        for approval_type in self.filtered(lambda record: record.model_id):
            action_name = '%s - View Approval History' % approval_type.name
            action = self.env['ir.actions.server'].sudo().search([
                ('name', '=', action_name),
                ('model_id', '=', approval_type.model_id.id),
            ], limit=1)
            code = (
                "action = {\n"
                "    'name': 'Approval History',\n"
                "    'type': 'ir.actions.act_window',\n"
                "    'res_model': 'sh.approval.request',\n"
                "    'view_mode': 'list,form',\n"
                "    'domain': [('res_model', '=', '%s'), ('res_id', 'in', records.ids)],\n"
                "}\n"
            ) % approval_type.model
            action_vals = {
                'name': action_name,
                'model_id': approval_type.model_id.id,
                'binding_model_id': approval_type.model_id.id,
                'binding_type': 'action',
                'binding_view_types': 'list,form',
                'state': 'code',
                'code': code,
            }
            if action:
                action.write(action_vals)
            else:
                self.env['ir.actions.server'].sudo().create(action_vals)

    def _remove_manual_server_action(self):
        """Remove auto-generated manual approval actions for these types."""
        for approval_type in self.filtered(lambda record: record.model_id):
            manual_actions = self.env['ir.actions.server'].sudo().search([
                ('name', '=', '%s - Manual Submit for Approval' % approval_type.name),
                ('model_id', '=', approval_type.model_id.id),
            ])
            manual_actions.unlink()

    def _remove_history_server_action(self):
        """Remove auto-generated approval history actions for these types."""
        for approval_type in self.filtered(lambda record: record.model_id):
            history_actions = self.env['ir.actions.server'].sudo().search([
                ('name', '=', '%s - View Approval History' % approval_type.name),
                ('model_id', '=', approval_type.model_id.id),
            ])
            history_actions.unlink()
