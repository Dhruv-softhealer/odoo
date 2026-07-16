# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import api, models, _
from odoo.models import BaseModel
from odoo.exceptions import UserError


def _approval_engine_available(env):
    """Return whether the approval engine model is loaded in the current registry."""
    return 'sh.approval.engine' in env.registry.models


class BaseModelExtend(models.AbstractModel):
    _inherit = 'base'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not _approval_engine_available(self.env):
            return records
        self.env['sh.approval.engine']._trigger_for_records(records, 'create')
        return records

    def write(self, vals):
        changed_fields = list(vals.keys())
        if not _approval_engine_available(self.env):
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
