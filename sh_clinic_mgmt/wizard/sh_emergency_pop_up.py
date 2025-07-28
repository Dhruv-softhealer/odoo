# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields

class EmergencyCaseWizard(models.Model):
    _name = 'sh.emergency.case.wizard'
    _description = 'Emergency Case Confirmation'

    sh_message = fields.Char(default="Do you want to switch to emergency case?")
    
    
    # ===================================== Confirm Button for Emergency Case ===========================================
    
    def action_confirm(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            record = self.env['sh.appointment'].browse(active_id)
            record.write({'sh_emergency_case': True})