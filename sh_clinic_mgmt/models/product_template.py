# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields
from datetime import date

class Medicine(models.Model):
    _inherit = 'product.template'
    
    sh_medicine_type = fields.Many2one('sh.medicine.type', string="Medicine Type")
    sh_brand = fields.Char(string="Brand")
    sh_side_effect = fields.Char(string="Side Effect")
    sh_provided_by_us = fields.Boolean(string="Provided By Us?", tracking=True)
    