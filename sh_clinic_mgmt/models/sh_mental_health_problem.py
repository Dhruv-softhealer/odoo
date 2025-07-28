# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class MentalHealthProblem(models.Model):
    _name = 'sh.mental.health.problem'
    _description = 'Mental Health Problem'
    
    name = fields.Char(string="Mental Health Problem", required=True)