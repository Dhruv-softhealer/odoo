# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class ChronicCondition(models.Model):
    _name = 'sh.chronic.condition'
    _description = 'Chronic Condition'
    
    name = fields.Char(string="Chronic Condition", required=True)