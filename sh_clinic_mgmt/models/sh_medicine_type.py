# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class MedicineType(models.Model):
    _name = 'sh.medicine.type'
    _description = 'Medicine Type'
    
    name = fields.Char(string="Disease Category", required=True,  tracking=True)
    description = fields.Char(string="Description")