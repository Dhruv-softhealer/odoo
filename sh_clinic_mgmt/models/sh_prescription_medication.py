# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class Prescription_Madication(models.Model):
    _name = 'sh.prescription.madication'
    _description = 'Prescription & Madication'
    
    
    sh_prescription_o2m_id = fields.Many2one('sh.appointment')
    sh_medicine_id = fields.Many2one('sh.medicine', required=True, tracking=True, string="Medicine Name")
    sh_medicine_type_id = fields.Many2one('sh.medicine.type', related="sh_medicine_id.sh_type", string="Medicine Type")
    sh_dosage_duration = fields.Date(string="Date", required=True)
    sh_morning = fields.Boolean(string="Morning")
    sh_afternoon = fields.Boolean(string="Afternoon")
    sh_evening = fields.Boolean(string="Evening")
    sh_night = fields.Boolean(string="Night")
    sh_late_night = fields.Boolean(string="Late Night")
    sh_instruction = fields.Selection([
        ('after_meal', 'After Meal'),
        ('before_meal', 'Before Meal')
    ], string="Instruction", required=True)
    sh_advice = fields.Html(string="Advice Given")