# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.


from datetime import datetime, timedelta
from odoo import _, models, api, fields
from odoo.exceptions import ValidationError

class Slots(models.Model):
    _name = 'sh.slots'
    _description = 'Slots'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    
    
    name = fields.Char(string="Slot Number", default=lambda self: _("New"), readonly=True, tracking=True)
    doctor_id = fields.Many2one('hr.employee',string='Doctor Name',required=True,tracking=True, domain="[('job_id.name', '=', 'Doctor')]")
    sh_slot_time = fields.Float(string="Slot Time(In Min)", required=True, tracking=True)
    sh_allowed_patients = fields.Integer(string="Allowed Patients", tracking=True, required=True)
    sh_pre_booking = fields.Float(string="Pre-Booking Time(In Min)", tracking=True)
    sh_start_date = fields.Date(string="Start Date", required=True, tracking=True)
    sh_end_date = fields.Date(string="End Date", required=True, tracking=True)
    sh_cancel_time = fields.Float(string="Allow Cancelling(In Min)", required=True)
    
    sh_schedule_line = fields.One2many('sh.slot.schedule', 'sh_slot_id', string="Appointment Slots")
    
    sh_state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('booked', 'Booked')
    ],default="draft", tracking=True)
    
    
    
    def compute_slot_stage(self):
        for rec in self:
            is_fully_booked = True
            for line in rec.sh_schedule_line:
                allowed = rec.sh_allowed_patients
                if len(line.sh_appointment_line) < allowed:
                    is_fully_booked = False
                    break
            rec.sh_state = 'booked' if is_fully_booked else 'published'
            
    
    # ================================= SEQUENCE ==================================
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', ("New")) == ("New"):
                seq_date = fields.Datetime.context_timestamp(
                    self, fields.Datetime.to_datetime(vals['create_date'])
                ) if 'create_date' in vals else None
                vals['name'] = self.env['ir.sequence'].with_company(vals.get('company_id')).next_by_code(
                    'sh.slots', sequence_date=seq_date) or _("New")
        return super().create(vals_list)
    
    
    
    # ================================= Date Constrain ==================================
    
    @api.constrains('sh_start_date', 'sh_end_date')
    def _check_date(self):
        for rec in self:
            if rec.sh_start_date and rec.sh_end_date:
                if rec.sh_end_date < rec.sh_start_date:
                    raise ValidationError("End Date cannot be earlier than Start Date.")
                
    # ======================================= Publish Slot ==========================================
                
    def publish_appointment(self):
        self.sh_state = 'published'
        
    # ======================================= Slot Generation ========================================
            
            
    def generate_slot(self):
        print("\n\n\n\nrun successfully")
        if not self.sh_slot_time:
            raise ValidationError("Slot time must be defined.")
 
        if self.sh_start_date and self.sh_end_date:
            self.sh_schedule_line.unlink()
 
            slot_minutes = int(self.sh_slot_time * 60)
            calendar_id = self.doctor_id.resource_calendar_id
            
            if not calendar_id:
                raise ValidationError("No working hours defined for current doctor.")
 
            current_date = self.sh_start_date
            while current_date <= self.sh_end_date:
                
                weekday = str(current_date.weekday())
 
                all_lines = calendar_id.attendance_ids.filtered(lambda a: a.dayofweek == weekday)
                if not all_lines:
                    current_date += timedelta(days=1)
                    continue
 
                working_lines = all_lines.filtered(lambda a: a.day_period != 'lunch')
                working_lines = sorted(working_lines, key=lambda a: a.hour_from)
 
                for line in working_lines:
                    start_dt = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=line.hour_from)
                    end_dt = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=line.hour_to)
 
                    while start_dt + timedelta(minutes=slot_minutes) <= end_dt:
                        slot_start_time = start_dt
                        slot_end_time = start_dt + timedelta(minutes=slot_minutes)
                        
                        start_time_float = slot_start_time.hour + slot_start_time.minute / 60.0
                        end_time_float = slot_end_time.hour + slot_end_time.minute / 60.0
                        self.env['sh.slot.schedule'].create({
                            'sh_slot_id': self.id,
                            'sh_appointment_line': False,
                            'sh_date': current_date,
                            'sh_start_time': start_time_float,
                            'sh_end_time': end_time_float,
                        })
 
                        start_dt = slot_end_time
                current_date += timedelta(days=1)
                
    # ======================================= Slot Overlapping ========================================
    
    
    @api.constrains('doctor_id', 'sh_start_date', 'sh_end_date')
    def _check_overlapping_slots(self):
        for rec in self:
            overlapping_slots = self.search([
                ('id', '!=', rec.id),
                ('doctor_id', '=', rec.doctor_id.id),
                ('sh_start_date', '<=', rec.sh_end_date),
                ('sh_end_date', '>=', rec.sh_start_date),
            ])
            if overlapping_slots:
                print("\n\n\n\n\noverlapping_slots--------------->", overlapping_slots.sh_start_date)
                raise ValidationError(
                    f"Doctor {rec.doctor_id.name} already has a slot between {overlapping_slots.sh_start_date} and {overlapping_slots.sh_end_date}. Please change the date or timing."
                )
