# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from datetime import datetime, timedelta
from venv import logger
from odoo import Command, _, models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.sql_db import timedelta
from odoo.tools.date_utils import date
from collections import defaultdict
from odoo.addons.portal.models.portal_mixin import PortalMixin


class Appointment(models.Model):
    _name = 'sh.appointment'
    _description = 'Appointment'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    
    # Header Page
    
    name = fields.Char(string="Appointment Number", required=True, tracking=True, readonly=True, default=lambda self: _('New'))
    sh_patient_id = fields.Many2one('res.partner', string="Patient Name", required=True, tracking=True)
    sh_doctor_id = fields.Many2one('hr.employee', string="Doctor Name", required=True, tracking=True, 
    domain=[('job_id.name','=','Doctor')]
    )
    sh_doctor_specialization = fields.Char(string="Doctor Specialization", related="sh_doctor_id.sh_specialization", tracking=True)
    sh_date = fields.Date(string="Date", required=True, tracking=True)
    sh_slot_id = fields.Many2one('sh.slots',related="sh_slt_id.sh_slot_id", store=True, string='Slot')
    sh_slt_id = fields.Many2one('sh.slot.schedule',required=True,string='Slot', tracking=True)
    sh_expected_revenue = fields.Float(string="Case Charges", tracking=True, readonly=True)
    sh_emergency_case = fields.Boolean(string="Emergency Case", tracking=True)
    
    
    # Patient Details 

    sh_email = fields.Char(string="Email", related="sh_patient_id.email", store=True, tracking=True)
    sh_phone = fields.Char(string="Phone", related="sh_patient_id.phone", required=True, readonly=False, tracking=True)
    sh_blood_group = fields.Selection(string="Blood Group", related="sh_patient_id.sh_blood_group", tracking=True)
    sh_birth_date = fields.Date(string="Birth Date", related="sh_patient_id.sh_birth_date", tracking=True)
    sh_age = fields.Char(string="Age", related="sh_patient_id.sh_age", tracking=True)
    sh_visit_type = fields.Selection([
        ('new', 'New'),
        ('old', 'Old')
    ], string="Visit Type", required=True, readonly=True, tracking=True)
    sh_last_visited = fields.Date(string="Last Visited", tracking=True, related="sh_patient_id.sh_last_visit_date")
    
    
    # Disease Details
    
    sh_disease_line = fields.One2many('sh.disease.detail', 'sh_disease_o2m_id')
    
    
    # Prescription & Medication 
    
    sh_prescription_line = fields.One2many('sh.prescription.madication', 'sh_prescription_o2m_id')
    
    # Personal medical info
    
    sh_lifestyle_factors_ids = fields.Many2many('sh.life.style.fector', related="sh_patient_id.sh_life_style_fector_ids", string="LifeStyle Fector")
    sh_mental_health_issues_ids = fields.Many2many('sh.mental.health.problem', related="sh_patient_id.sh_mental_health_problem_ids", string="Mental Health Issues")
    sh_chronic_conditions_ids = fields.Many2many('sh.chronic.condition', related="sh_patient_id.sh_cronic_condition_ids", string="Chronic Condition")
    sh_dietary_preferences = fields.Selection(string="Dietary Preferences", related="sh_patient_id.sh_dietary_preferences", tracking=True)
    sh_allergy_ids = fields.Many2many('sh.allergies', string="Allergies", related="sh_patient_id.sh_allergy_ids")
    
    # Emergency Handling info
    
    sh_priority_level = fields.Selection([
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string="Priority Level", tracking=True)
    sh_doctor_notified = fields.Boolean(string="Doctor Notified?")
    sh_assigned_doctor = fields.Many2one('hr.employee', string="Assigned Doctor", tracking=True)
    sh_immediate_check_in = fields.Boolean(string="Immediate Check-in?", tracking=True)
    sh_emergency_slot_bypass = fields.Boolean(string="Emergency Slot Bypass", tracking=True)
    sh_walk_in_case = fields.Boolean(string="Walk In Case?", tracking=True)
    sh_checked_in = fields.Boolean(string="Checked In?")
    
    sh_state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('completed_appointment', 'Completed Appointment'),
        ('cancelled_appointment', 'Cancelled Appointment'),
    ], 
    default='new',
    tracking=True
    )
    
    # Portal Report Access
    
    def get_portal_url(self, suffix=None, download=None, report_type=None, query_string=None, anchor=None, **kwargs):
        self.ensure_one()
        url = self.access_url + '%s?access_token=%s%s%s%s%s' % (
            suffix if suffix else '',
            self._portal_ensure_token(),
            '&report_type=%s' % report_type if report_type else '',
            '&download=true' if download else '',
            query_string if query_string else '',
            '#%s' % anchor if anchor else ''
        )
        return url
    
    def _get_report_base_filename(self):
        self.ensure_one()
        return 'APT-%s' % (self.name)
    
    # ===================================== Portal Access ===========================================
    
    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            order.access_url = f'/my/appointments/{order.id}'

    
    # ===================================== Stages ===========================================
        

    def check_in(self):
        self.sh_state = 'in_progress'
        self.sh_checked_in = True
        
    def move_to_done(self):
        self.sh_state = 'completed_appointment'
        self.sh_patient_id.sh_last_visit_date = date.today()
        return {
        'type': 'ir.actions.client',
        'tag': 'reload',
        }
        
    def unlock_record(self):
        self.sh_state = 'in_progress'
            
    
    
    def cancel_record(self):
        self.sh_state = 'cancelled_appointment'
        for record in self:
            if record.sh_slt_id:
                curr_time = fields.Datetime.now()
                start = record.sh_slt_id.sh_start_time
                slot_cancel_time_limit = record.sh_slot_id.sh_cancel_time
                
                if start - curr_time.hour <= slot_cancel_time_limit:
                    raise UserError(f'You can not cancel slot before {slot_cancel_time_limit} hours')
                
                record.sh_slt_id.write({
                    'sh_appointment_line': [Command.unlink(record.id)]
                })
                return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Success',
                            'message': 'Appointment cancelled successfully.',
                            'type': 'success',  
                            'sticky': False,
                        }
                    }
            mail_template = self.env.ref('sh_clinic_mgmt.mail_template_cancel_appointment')
            if mail_template:
                mail_template.send_mail(record.id, force_send=True)
        
    
    # ======================================= Emergence Case ==========================================
        
     
    @api.onchange('sh_emergency_case')
    def onchange_emergency_case(self):
        if self.sh_emergency_case:
            self.sh_doctor_notified = True
            self.sh_assigned_doctor = self.sh_doctor_id
            
     
    # ======================================= Date Validation & Apply Charges ==========================================
        
    @api.onchange('sh_date')
    def onchage_state_and_charge(self):
        if self.sh_doctor_id and self.sh_patient_id:
            
            if self.sh_date < fields.date.today():
                self.sh_date = False
                return {
                    'warning': {
                        'title': "Invalid Date",
                        'message': "Date cannot be set earlier than today."
                    }
                }
                
            case_days = self.env.company.sh_case_days
            
            if (self.sh_date - self.sh_last_visited).days > case_days:
                
                self.sh_visit_type = 'new'
                self.sh_expected_revenue = self.sh_doctor_id.sh_new_case_charges
                
            else:
                self.sh_visit_type = 'old'
                self.sh_expected_revenue = self.sh_doctor_id.sh_old_case_charges

 
# ======================================== Assign Appointment to Slot =========================================
            

    def assign_slot_line(self):
        print("\n\n\n\n-=-=-=-=--=-=-")
        for rec in self:
            if rec.sh_slt_id and rec.sh_date:
                if not rec.sh_emergency_slot_bypass:
                    if len(rec.sh_slt_id.sh_appointment_line) >= rec.sh_slot_id.sh_allowed_patients:
                        raise ValidationError(
                            f"Only {rec.sh_slot_id.sh_allowed_patients} patients allowed in {rec.sh_slt_id.name}."
                            )
                
                rec.sh_slt_id.write({
                    'sh_appointment_line': [Command.link(rec.id)]
                    })
                print("\n\n\n\n-=-=-=-=--=-=-rec.sh_slt_id",rec.sh_slt_id)
                

# ================================== Sequence =======================================
   
    @api.model_create_multi
    def create(self, vals):
        # sh_patient_id = vals.get('sh_patient_id')
        # sh_doctor_id = vals.get('sh_doctor_id')

        # previous_appointment = self.search([('sh_patient_id', '=', sh_patient_id), ('sh_doctor_id', '!=', sh_doctor_id)], limit=1)

        # if previous_appointment:
        #     # If there's a different doctor, apply new case charges (500)
        #     vals['case_charges'] = 500
        # else:
        #     # If the doctor is the same, use existing charges
        #     existing_case_charges = previous_appointment.case_charges if previous_appointment else 0.0
        #     vals['case_charges'] = existing_case_charges or 500
        

        print("\n\n\n\nportal create===============>>>>", vals)
        for val in vals:
            if val['sh_date']:
                booking_dt = fields.Datetime.from_string(val['sh_date'])

                local_booking_dt = fields.Datetime.context_timestamp(self, booking_dt)
                booking_str = local_booking_dt.strftime('%y%m%d-%H%M')
 
                now_dt = fields.Datetime.context_timestamp(self, datetime.now())
                current_str = now_dt.strftime('%y%m%d-%H%M')
                
                #============================ pre-booking validation =================================
                
                if val.get('sh_slt_id') and not val.get('sh_emergency_slot_bypass'):
                    rec = self.env['sh.slot.schedule'].browse(val['sh_slt_id'])
                    
                    if rec.sh_slot_id.sh_pre_booking:
                        pre_booking_hour = rec.sh_slot_id.sh_pre_booking
                        diff = (local_booking_dt - now_dt).total_seconds() / 3600.0
            
                        if diff < pre_booking_hour:
                            raise ValidationError(f"A minimum advance booking of {pre_booking_hour} hours is required.")
 
                seq = self.env['ir.sequence'].next_by_code('sh.appointment') or '000'
                val['name'] = f'APT-B{booking_str}-C{current_str}-{seq}'
                val['sh_state'] = 'new'
        record = super().create(vals)
        record.assign_slot_line()
        return record
 
    def write(self, vals):
        res = super(Appointment, self).write(vals)
 
        if 'sh_date' in vals or 'sh_slt_id' in vals or 'sh_emergency_slot_bypass' in vals:
            if vals.get('sh_date'):
                booking_dt = fields.Datetime.from_string(vals['sh_date'])
                local_booking_dt = fields.Datetime.context_timestamp(self, booking_dt)
 
            now_dt = fields.Datetime.context_timestamp(self, datetime.now())
            
            
            #============================ pre-booking validation =================================
            
            if vals.get('sh_slt_id') and not vals.get('sh_emergency_slot_bypass'):
                rec = self.env['sh.slot.schedule'].browse(vals['sh_slt_id'])
                if rec.sh_slot_id.sh_pre_booking:
                    pre_booking_hour = rec.sh_slot_id.sh_pre_booking
                    diff = (local_booking_dt - now_dt).total_seconds() / 3600.0
                   
                    if diff < pre_booking_hour:
                        raise ValidationError(f"A minimum advance booking of {pre_booking_hour} hours is required.")
 
            slot_line = self.env['sh.slot.schedule'].search([('sh_slot_id', '=', self.sh_slt_id.id),('sh_appointment_line', 'in', self.id)],limit=1)
                        
            slot_line.write({
                'sh_appointment_line': [Command.link(self.id)]  
            })
                        
            self.assign_slot_line()
        return res