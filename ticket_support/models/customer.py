# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models , api

class Customer(models.Model):
    _inherit='res.partner'
    
    ticket_ids = fields.One2many('support.ticket' , 'partner_id' )
    sh_ticket_count = fields.Integer(compute='_compute_ticket_count')
    
    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        for record in self:
            record.sh_ticket_count = len(record.ticket_ids)
    
    def nav_related_ticket(self):
        return{
            'name': 'Related Ticket',
            'domain': [('id', '=', self.ticket_ids.ids)],
            'views': [[False, 'list'], [False, 'form']],
            'res_model': 'support.ticket',
            'type': 'ir.actions.act_window',
        }
        
            
