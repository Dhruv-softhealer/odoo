# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields
from datetime import date

class HR_Job(models.Model):
    _inherit = 'hr.job'
    
    
    sh_code = fields.Char(string="Job Code", tracking=True, required=True)
    sh_department = fields.Many2one('hr.department', string="Department", tracking=True, required=True)
    description = fields.Char(string="Description")
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        store=True,
    )
    sh_salary_range = fields.Monetary(string="Salary Range")
    sh_required_qualification = fields.Char(string="Required Qualification")
    sh_experience_required = fields.Integer(tracking=True, string="Experience Required")