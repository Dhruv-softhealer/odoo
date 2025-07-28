# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields
from datetime import date

class Setting(models.TransientModel):
    _inherit = 'res.config.settings'
    
    
    sh_case_days = fields.Integer(string="Expired Case Days", related="company_id.sh_case_days", readonly=False)
    
    
class AccessSetting(models.Model):
    _inherit = 'res.company'
    
    sh_case_days = fields.Integer()