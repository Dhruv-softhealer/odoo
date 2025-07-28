# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api

class Medicine(models.Model):
    _name = 'sh.medicine'
    _description = 'Medicine'
    
    name = fields.Char(string="Name", required=True, readonly=False,  tracking=True)
    sh_type = fields.Many2one('sh.medicine.type', string="Medicine Type")
    sh_provided_by_us = fields.Boolean(tracking=True, string="Provided By Us?")
    sh_product_id = fields.Many2one('product.template', string="Product") 
    
    def create_product(self):
        return{
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model' : 'product.template',
            'context' : {
                'default_name' : self.name,
                'default_sh_medicine_type' : self.sh_type.id
                },
            'target' : 'new',
        }
        
    @api.onchange('sh_product_id')
    def onchange_product(self):
        self.name = self.sh_product_id.name