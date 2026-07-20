# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import test_python_expr


class ShApprovalLevel(models.Model):
    """Ordered approval stage within an approval type."""

    _name = 'sh.approval.level'
    _description = 'Dynamic Approval Level'
    _order = 'sequence, id'

    approval_type_id = fields.Many2one('sh.approval.type', required=True, ondelete='cascade', index=True)
    company_ids = fields.Many2many('res.company', string='Company Filter', help='If specified, this level will only apply to records belonging to these companies.')
    sequence = fields.Integer(required=True, default=10, index=True)
    name = fields.Char(required=True)
    approval_method = fields.Selection(
        [
            ('group', 'Access Group'),
            ('job', 'Job Position'),
            ('python', 'Dynamic Code (Python)'),
        ],
        required=True,
        default='group',
    )
    group_id = fields.Many2one('res.groups', string='Access Group')
    job_id = fields.Many2one('hr.job', string='Job Position')
    python_code = fields.Text(
        string='Python Expression',
        help='Expression must return a res.users record or a res.users recordset. Variables: record, env, user.',
    )
    alternative_user_id = fields.Many2one('res.users', string='Alternative Approver')
    escalation_timeout = fields.Float(
        string='Escalation Timeout',
        default=0.0,
        help='Timeout in hours. Leave 0 to disable timeout escalation.',
    )



    active = fields.Boolean(default=True, string='Active')

    @api.constrains('approval_method', 'group_id', 'job_id', 'python_code')
    def _check_approval_method_config(self):
        """Validate method-specific approver configuration."""
        for level in self:
            if level.approval_method == 'group' and not level.group_id:
                raise ValidationError(_('Please select an access group for group-based approval.'))
            if level.approval_method == 'job' and not level.job_id:
                raise ValidationError(_('Please select a job position for job-based approval.'))
            if level.approval_method == 'python':
                if not level.python_code:
                    raise ValidationError(_('Please enter a Python expression for dynamic approval.'))
                message = test_python_expr(expr=level.python_code.strip(), mode='eval')
                if message:
                    raise ValidationError(_('Invalid Python expression: %s') % message)

    def unlink(self):
        if not self.env.user.has_group('sh_dynamic_approval.group_sh_dynamic_approval_admin'):
            raise ValidationError(_('Only an Administrator can delete an Approval Level.'))
            
        # Forcefully delete referencing lines to prevent database constraint errors
        for level in self:
            lines = self.env['sh.approval.line'].sudo().search([('level_id', '=', level.id)])
            if lines:
                lines.unlink()
                
        return super().unlink()
