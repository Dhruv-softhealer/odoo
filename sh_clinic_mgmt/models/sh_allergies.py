# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class Allegies(models.Model):
    _name = 'sh.allergies'
    _description = 'Allergies'
    
    name = fields.Char(string="Allergies", required=True)