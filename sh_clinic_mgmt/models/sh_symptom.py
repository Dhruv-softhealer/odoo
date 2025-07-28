# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class Symptom(models.Model):
    _name = 'sh.symptom'
    _description = 'Symptom'
    
    name = fields.Char(string="Symptom", required=True, tracking=True)