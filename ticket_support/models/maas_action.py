# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models , api

class Mass_action(models.Model):
    _name = 'mass.action'
    _description = 'Mass Action'
    
    stage  = fields.Selection( [ ('new' , 'New') , ('inprogress' , 'Inprogress') , ('resolved' , 'Resolved') , ('close' , 'Close')] , default='new' ,String='Stage')

    
    def close_stage_method(self):     
        model=self.env.context['active_model']
        ids=self.env.context['active_ids']
        rec=self.env[model].browse(ids)
        rec.write({'stage':self.stage})   
        rec.make_invoice()
        
        
    