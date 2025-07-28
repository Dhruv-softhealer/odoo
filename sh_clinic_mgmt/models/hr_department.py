# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields

class Department(models.Model):
    _inherit = 'hr.department'
    
    sh_code = fields.Char(string="Department Code", required=True, tracking=True)
    description = fields.Char(string="Description")