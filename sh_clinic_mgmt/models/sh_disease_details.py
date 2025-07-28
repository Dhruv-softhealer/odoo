# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class DiseaseDetail(models.Model):
    _name = 'sh.disease.detail'
    _description = 'Disease Detail'
    
    
    sh_disease_o2m_id = fields.Many2one('sh.appointment')
    sh_disease_name = fields.Many2one('sh.disease', string="Disease Name", required=True, tracking=True)
    sh_disease_category = fields.Many2many('sh.disease.category', related="sh_disease_name.sh_category_ids", readonly=False)
    sh_symptoms_ids = fields.Many2many('sh.symptom', string="Symptoms")
    sh_severity = fields.Selection([
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5')
    ], string="Severty")
    description = fields.Html(string="Description")