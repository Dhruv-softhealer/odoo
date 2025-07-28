# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class Disease(models.Model):
    _name = 'sh.disease'
    _description = 'Disease'
    
    name = fields.Char(string="Disease", required=True)
    sh_category_ids = fields.Many2many('sh.disease.category', string="Disease Category")
    sh_symptom_ids = fields.Many2many('sh.symptom', string="Symptoms")
    description = fields.Char(string="Description")
    sh_treatment_plan = fields.Html(string="Treatment Plan")