# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import api, models, fields
from datetime import date

class Patient(models.Model):
    _inherit = 'res.partner'
    
    sh_birth_date = fields.Date(string="Date Of Birth", required=True)
    sh_age = fields.Char(string="Age", compute="_compute_age")
    sh_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
        ],string="Gender")
    
    sh_blood_group = fields.Selection([
        ('a+', 'A+'),
        ('a-', 'A-'),
        ('b+', 'B+'),
        ('b-', 'B-'),
        ('ab+', 'AB+'),
        ('ab-', 'AB-'),
        ('o+', 'O+'),
        ('o-', 'O-')
    ], string="Blood Group")
    sh_dietary_preferences = fields.Selection([
        ('vegetarian', 'Vegetarian'),
        ('gluten_free', 'Gluten-Free'),
        ('non_vegetarian', 'Non Vegetarian'),
        ('vegan', 'Vegan'),
    ], string="Dietary Preferences")
    sh_life_style_fector_ids = fields.Many2many('sh.life.style.fector', string="Life Style Fector")
    sh_mental_health_problem_ids = fields.Many2many('sh.mental.health.problem', string="Mental Health Problem")
    sh_allergy_ids = fields.Many2many('sh.allergies', string="Allergies")
    sh_allergies_description = fields.Char(string="Allergies Description")
    sh_cronic_condition_ids = fields.Many2many('sh.chronic.condition', string="Chronic Condition")
    sh_regular_medicine = fields.Char(string="Regular Medicine Take If Any?")
    sh_mobility_status = fields.Selection([
        ('wheelchair', 'WheelChair'),
        ('walker', 'Walker'),
        ('crutches', 'Crutches'),
    ], string="Mobility Status")
    sh_report_name = fields.Char('sh_report_name')
    sh_report = fields.Binary(string="Reports")
    
    
    sh_last_visit_date = fields.Date(string='Last Visit Date', default=fields.Date.today)
    
    @api.depends('sh_birth_date')
    def _compute_age(self):
        for rec in self:
            if rec.sh_birth_date:
                current_date = date.today()
                age = current_date.year - rec.sh_birth_date.year - (
                    (current_date.month, current_date.day) < (rec.sh_birth_date.month, rec.sh_birth_date.day)
                )
                rec.sh_age = str(age)
            else:
                rec.sh_age = 0

    @api.onchange('sh_birth_date')
    def _onchange_sh_birth_date(self):
        if self.sh_birth_date:
            if self.sh_birth_date > fields.date.today():
                self.sh_birth_date = False
                return {
                    'warning': {
                        'title': "Invalid Date",
                        'message': "Birth date cannot be set greater than today."
                    }
                }