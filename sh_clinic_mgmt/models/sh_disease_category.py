# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class DiseaseCategory(models.Model):
    _name = 'sh.disease.category'
    _description = 'Disease Category'
    
    name = fields.Char(string="Disease Category", required=True)
    description = fields.Char(string="Description")