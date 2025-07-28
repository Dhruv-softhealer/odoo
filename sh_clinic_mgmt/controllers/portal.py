# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import http, _
from odoo.osv.expression import AND, OR
from odoo.http import request
from odoo.addons.portal.controllers import portal
from odoo.tools import date_utils, groupby as groupbyelem
from operator import itemgetter
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo.exceptions import AccessError,MissingError
from odoo import fields
import requests
# import logging
import json


class AppointmentPortal(CustomerPortal):

    # Portal Home Values

    def _prepare_home_portal_values(self, counters):
            values = super()._prepare_home_portal_values(counters)
            if 'appointment_count' in counters:
                values['appointment_count'] = request.env['sh.appointment'].sudo().search_count([
                    ('sh_patient_id', '=', request.env.user.partner_id.id)
                ])
            return values

    def _search_bar_domain(self,search,search_in):
        # print("\n\n\n", search_in)
        search_domains = []
        if search_in in ('all', 'name'):
            search_domains.append([('name', 'ilike', search)])
        if search_in in ('all', 'doctor'):
            search_domains.append([('sh_doctor_id.name', 'ilike', search)])
        if search_in in ('all', 'sh_date'):
            search_domains.append([('sh_date', 'ilike', search)])
        if search_in in ('all', 'sh_state'):
            search_domains.append([('sh_state', 'ilike', search)])

        return OR(search_domains) if search_domains else []
    
    
    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_appointments(self, page=1, sortby=True, filterby="all", groupby='create_by', search=None, search_in='name', **kw):
        Appointment = request.env['sh.appointment'].sudo()
        # print("\n\n\n", Appointment)
        partner_id = request.env.user.partner_id.id
        # print("\n\n\n", partner_id)

        domain = [('sh_patient_id', '=', partner_id)]
        
        appointments_count = Appointment.search_count(domain)
        # print("\n\n\n", appointments_count)
        
        # Search and Filter Logic
        
        searchbar_sortings = {
            'new': {'label': _('Appointment'), 'order': 'create_date desc'},
            'doctor': {'label': _('Doctor'), 'order': 'sh_doctor_id'},
            'stage': {'label': _('Stage'), 'order': 'sh_state'},
        }

        if sortby not in searchbar_sortings:
            sortby = 'doctor'

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'new': {'label': _('New'), 'domain': [('sh_state','=','new')]},
            'in_progress': {'label': _('In-Progress'), 'domain': [('sh_state','=','in_progress')]},
            'completed_appointment': {'label': _('Completed Appointment'), 'domain': [('sh_state','=','completed_appointment')]},
            'cancelled_appointment': {'label': _('Cancelled Appointment'), 'domain': [('sh_state','=','cancelled_appointment')]},
        }

        searchbar_inputs = {
            'all': {'label': _('Search in All'), 'input': 'all'},
            'name': {'label': _('Search in Name'), 'input': 'name'},
            'doctor': {'label': _('Search in Doctor'), 'input': 'doctor'},
            'sh_date': {'label': _('Search in Date'), 'input': 'sh_date'},
            'sh_state': {'label': _('Search in Stage'), 'input': 'sh_state'}
        }

        searchbar_groupby = {
            # 'none': {'label': _('None')},
            'create_by': {'input': 'create_by', 'label': _('None')},
            'doctor': {'input': 'sh_doctor_id', 'label': _('Doctor')},
            'date': {'input': 'sh_date', 'label': _('Date')},
            'state': {'input': 'sh_state', 'label': _('State')},
        }

        if filterby:
            domain += searchbar_filters[filterby]["domain"]

        search_bar_domain = self._search_bar_domain(search,search_in)
        # print("\n\n\n\n", search_bar_domain)
        if search_bar_domain:
            domain = AND([domain,search_bar_domain])
        
        # Sorting & Pagination Logic
        
        order = searchbar_sortings[sortby]["order"]
        url = "/my/appointments"
        pager = portal.pager(
            url=url,
            total=appointments_count,
            page=page,
            step=20,
            url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'filterby': filterby, 'groupby': groupby},
        )
        
        if groupby == 'create_by':
            order = "create_uid, %s" % order
        elif groupby == 'doctor':
            order = "sh_doctor_id, %s" % order
        elif groupby == 'date':
            order = "sh_date, %s" % order
        elif groupby == 'state':
            order = "sh_state, %s" % order
        else:
            order = order 
        
        
        appointments = Appointment.search(domain, limit=20, offset=pager['offset'], order=order)      
        print("\n\n\n", appointments)

        if groupby == 'create_by':
            grouped_tickets = [Appointment.concat(
                *g) for k, g in groupbyelem(appointments, itemgetter('create_uid'))]
        elif groupby == 'doctor':
            grouped_tickets = [Appointment.concat(
                *g) for k, g in groupbyelem(appointments, itemgetter('sh_doctor_id'))]
        elif groupby == 'date':
            grouped_tickets = [Appointment.concat(
                *g) for k, g in groupbyelem(appointments, itemgetter('sh_date'))]
        elif groupby == 'state':
            grouped_tickets = [Appointment.concat(
                *g) for k, g in groupbyelem(appointments, itemgetter('sh_state'))]
        elif groupby == 'none' or not groupby:
            grouped_tickets = appointments

        # Prepare the response for rendering
        
        request.session['my_pager'] = appointments.ids
        # print("\n\n\n\n", temp)
        
        
        return request.render("sh_clinic_mgmt.portal_my_appointments", {
            'appointments': appointments,
            'pager': pager,
            'page_name': 'appointments',
            'grouped_tickets':grouped_tickets,
            
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
            
            'searchbar_inputs':searchbar_inputs,
            'search':search,
            'search_in':search_in,
            
            'searchbar_groupby': searchbar_groupby,
            'groupby': groupby,
            
            'default_url': url,
            
            'doctors': request.env['hr.employee'].sudo().search([('job_id.name', '=', 'Doctor')]),
            'slots': '',
            'selected_date': '',
            'csrf_token': request.csrf_token(),
        })
        
    # Pagination at Form Side
      
    def get_records_pager(self, ids, current):
        # print("\n\n\n\n", current.id)
        if current.id in ids and (hasattr(current, 'website_url') or hasattr(current, 'access_url')):
            attr_name = 'access_url' if hasattr(current, 'access_url') else 'website_url'
            idx = ids.index(current.id)
            prev_record = idx != 0 and current.browse(ids[idx - 1])
            next_record = idx < len(ids) - 1 and current.browse(ids[idx + 1])

            if prev_record and prev_record[attr_name] and attr_name == "access_url":
                prev_url = '%s?access_token=%s' % (prev_record[attr_name], prev_record._portal_ensure_token())
            elif prev_record and prev_record[attr_name]:
                prev_url = prev_record[attr_name]
            else:
                prev_url = prev_record

            if next_record and next_record[attr_name] and attr_name == "access_url":
                next_url = '%s?access_token=%s' % (next_record[attr_name], next_record._portal_ensure_token())
            elif next_record and next_record[attr_name]:
                next_url = next_record[attr_name]
            else:
                next_url = next_record

            return {
                'prev_record': prev_url,
                'next_record': next_url,
            }
        return {}

    # Portal Record Detail View
    
    @http.route(["/my/appointments/<int:appointment_id>"], type="http", auth="public", website=True)
    def my_portal_document(self, appointment_id, access_token=None, report_type=None, download=False):
        try:
            appointment = self._document_check_access('sh.appointment', appointment_id, access_token=access_token)
            print("\n\n\n", appointment)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # Report
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(
                model=appointment,
                report_type=report_type,
                report_ref='sh_clinic_mgmt.report_appointment_action',
                download=download
            )

        history = request.session.get('my_pager',[]) 


        record_pager = self.get_records_pager(history, appointment)

        return request.render("sh_clinic_mgmt.portal_appointment_detail", {
            "appointment": appointment,
            "page_name": "appointments",
            "prev_record": record_pager.get('prev_record'),
            "next_record": record_pager.get('next_record'),
        })

        
    # Book Appointment Page

    
    @http.route('/submit/appointment', type='http', auth="user", website=True, methods=["POST"], csrf=False)
    def submit_appointment(self, **post):
        patient = request.env.user.partner_id
        doctor_id = post.get('sh_doctor_id')
        slot_id = post.get('portal_slot')
        selected_date = post.get('sh_date')

        if not doctor_id or not slot_id or not selected_date:
            return request.redirect('/book/appointment')

        # Convert to date object
        selected_date_obj = fields.Date.to_date(selected_date)
        # print(f"\n\n\n\n\==========>>>> 305 selected_date_obj", selected_date_obj)
        doctor = request.env['hr.employee'].sudo().browse(int(doctor_id))
        case_days = request.env.company.sh_case_days

        # Get last visit (previous appointment before this date)
        last_apt = request.env['sh.appointment'].sudo().search([
            ('sh_patient_id', '=', patient.id),
            ('sh_date', '<', selected_date_obj)
        ], order='sh_date desc', limit=1)
        # print(f"\n\n\n\n\==========>>>> 308 case_days", last_apt.name)

        last_visited_date = last_apt.sh_date if last_apt else False
        diff_days = (selected_date_obj - last_visited_date).days if last_visited_date else 9999
        print(f"\n\n\n\n\==========>>>> 318 diff_days", diff_days)

        # Determine visit type and revenue
        if diff_days <= case_days:
            visit_type = 'old'
            expected_revenue = doctor.sh_old_case_charges
        else:
            visit_type = 'new'
            expected_revenue = doctor.sh_new_case_charges

        # Create the appointment
        rec_apt = request.env['sh.appointment'].sudo().create({
            'sh_patient_id': patient.id,
            'sh_doctor_id': int(doctor_id),
            'sh_date': post.get('sh_date'),
            'sh_slt_id': int(slot_id),
            'sh_phone': post.get('sh_phone'),
            'sh_last_visited': last_visited_date,
            'sh_visit_type': visit_type,
            'sh_expected_revenue': expected_revenue,
        })
        print("\n\n\n\n======rec_apt",rec_apt.name)


    @http.route('/portal/slotdata', type="http",auth="user",methods=['POST'],website=True,csrf=False)
    def sh_slot_data(self, **kw):
        dic = {}
        # print("\n\n\n\n====>kw.get('sh_date')",(kw.get('sh_doctor_id')))
        if kw.get('sh_date') and kw.get('sh_doctor_id'):
            sub_categ_list = []
            sub_categ_ids = request.env['sh.slot.schedule'].sudo().search(
                [('sh_date', '=', (kw.get('sh_date'))),('sh_slot_id.doctor_id','=',int(kw.get('sh_doctor_id')))])
            # print("\n\n\n\n====>sub_categ_ids",sub_categ_ids)
            
            for sub in sub_categ_ids:   
                sub_categ_dic = {
                    'id': sub.id,
                    'name': sub.name,
                }
                sub_categ_list.append(sub_categ_dic)
            dic.update({
                'sub_categories': sub_categ_list
            })
        else:
            dic.update({
                'sub_categories': []
            })
        return json.dumps(dic)