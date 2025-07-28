# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models , api , Command 
from odoo.exceptions import ValidationError
from datetime import datetime , timedelta

class Ticket_support(models.Model):
    _name = 'support.ticket'
    _description='Support'
    # _sql_constraints = [    
    #     ('unique_ticket',
    #      'UNIQUE(developer)',
    #      'A developer can only have one active ticket at a time.')
    # ]
    _inherit = ['mail.thread',
                'mail.activity.mixin',
                'utm.mixin',
                'mail.tracking.duration.mixin',
               ]

    
    name = fields.Char(string="Ticket")
    priority = fields.Selection( [('0', 'Low priority'),
    ('1', 'Medium priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),] , string='Priority', comapany_dependent=True)
    stage  = fields.Selection( [ ('new' , 'New') , ('inprogress' , 'Inprogress') , ('resolved' , 'Resolved') , ('close' , 'Close')] , default='new' ,String='Stage')
    developer = fields.Many2one('res.users', string='Developer')
    support_leader=fields.Many2one('res.users' , string="Support Leader")
    partner_id = fields.Many2one('res.partner',stiring="Customer")
    resolved_date = fields.Datetime()
    invoice_id = fields.Many2one('account.move', string="Invoice")
    task_title = fields.Text(string='Title')
    task_description = fields.Html(string='Description')
    
    def resolved_button(self):
        self.stage='resolved'
        self.write({'stage': 'resolved', 'resolved_date': fields.Datetime.now()})
        
    def close_button(self):
        self.stage='close'
      
    def inProgress_button(self):
        self.stage='inprogress'
        
    @api.constrains('developer') 
    def _developer_constrain(self):
         developers = self.env['support.ticket'].search([('developer', '=' , self.developer.id)]) 
         print("dev:::::::::::::::::",developers)
         for rec in developers:
             if  rec.stage == 'inprogress':
                 raise ValidationError('Developer already has a ticket in progress')
            
    @api.model
    def default_get(self, fields):
        defaults = super(Ticket_support , self).default_get(fields)
        defaults['priority']='1'
        return defaults
           
    @api.model_create_multi
    def create(self, vals_list): 
        for vals in vals_list:
                vals['name'] = self.env['ir.sequence'].next_by_code('support.ticket', sequence_date=datetime.now())  
        return super().create(vals_list)  
    
    def make_invoice(self):
      for rec in self:
         if rec.stage=='close':
          invoice = self.env['account.move'].create([{
                'partner_id':rec.partner_id.id,
                'move_type':'out_invoice',
                'invoice_date':fields.Date.today(),
                'invoice_line_ids':[Command.create({
                    'name':rec.name,
                    'quantity' : 1,
                    'price_unit' : 10
                })]
            }]) 
          rec.invoice_id=invoice.id
    
    
    # def write(self,vals):
    #     if vals.get('developer'):
    #         vals['stage'] = 'inprogress'         
    #     return super().write(vals)    
    
    def resolved_button(self):
        self.write({'stage': 'resolved', 'resolved_date': fields.Datetime.now()})

    def auto_close_resolved_tickets(self):
        deadline = fields.Datetime.now() - timedelta(days=7)
        tickets = self.search([('stage', '=', 'resolved'), ('resolved_date', '<=', deadline)])
        tickets.write({'stage': 'close'})   
        
    def nav_related_invoice(self):     
        return{
            'name': 'Related Ticket',
            'domain': [('id', '=', self.invoice_id.id)],
            'views': [[False, 'list'], [False, 'form']],
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
        }
        
    def close(self):
        return{
            'name': 'close',
            'target':'new',
            'type':'ir.actions.act_window',
            'res_model':'mass.action',
            'views': [ [False, 'form']],                     
        }  
        
    
    # for automatation     
        
    @api.model 
    def message_new(self, msg_dict, custom_values=None):
        vals = {
            'task_title':  msg_dict.get('subject') or ("No Subject"),
            'task_description': msg_dict.get('body'),
            'partner_id': msg_dict.get('author_id', True),
        }
        vals.update(custom_values or {})
        return self.create(vals)    