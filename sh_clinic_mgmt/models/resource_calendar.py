# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields

class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'
    
    sh_doctor_name = fields.Many2one('hr.employee', tracking=True, required=True, string="Doctor Name")