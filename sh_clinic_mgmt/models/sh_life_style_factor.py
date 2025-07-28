# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class LifeStyleFector(models.Model):
    _name = 'sh.life.style.fector'
    _description = 'Life Style Fector'
    
    name = fields.Char(string="Life Style Fector", required=True)