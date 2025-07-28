# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields
from datetime import date

class Doctor(models.Model):
    _inherit = 'hr.employee'
    
    sh_old_case_charges = fields.Monetary(string="Old Case Charges", tracking=True, required=True, default=300)
    sh_new_case_charges = fields.Monetary(string="New Case Charges", tracking=True, required=True, default=500)
    sh_specialization = fields.Char(string="Specialization", required=True)
    sh_user_login_access = fields.Boolean()