# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields
from collections import defaultdict


class AppointmentSummaryWizard(models.TransientModel):
    _name = 'sh.appointment.summary.wizard'
    _description = 'Appointment Summary Wizard'

    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    doctor_id = fields.Many2one('hr.employee', string='Doctor')

    def generate_report(self):
        data = {
            'from_date': self.from_date,
            'to_date': self.to_date,
            'doctor_id': self.doctor_id.name,
        }
        return self.env.ref('sh_clinic_mgmt.report_appointment_summary').report_action(self, data=data)


# ============================== Report ===================================
    
    
class AppointmentSummaryReport(models.AbstractModel):
    _name = 'report.sh_clinic_mgmt.appointment_summary_template'
    _description = 'Daily Appointment Summary Report'

    
    def _get_report_values(self, docids, data=None):
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        doctor_id = data.get('doctor_id')

        domain = [('sh_date', '>=', from_date), ('sh_date', '<=', to_date)]
        if doctor_id:
            domain.append(('sh_doctor_id', '=', doctor_id))

        appointments = self.env['sh.appointment'].search(domain)

        summary = defaultdict(lambda: {'total': 0, 'completed': 0, 'canceled': 0})
        for appt in appointments:
            date_str = appt.sh_date.strftime('%Y-%m-%d')
            summary[date_str]['total'] += 1
            if appt.sh_state == 'completed_appointment':
                summary[date_str]['completed'] += 1
            elif appt.sh_state == 'cancelled_appointment':
                summary[date_str]['canceled'] += 1

        report_data = [{'date': k, **v} for k, v in sorted(summary.items())]

        return {
            'doc_ids': docids,
            'doc_model': 'sh.appointment.summary.wizard',
            'data': data,
            'docs': report_data,
        }