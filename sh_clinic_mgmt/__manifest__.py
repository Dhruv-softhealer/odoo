# -*- coding: utf-8 -*-
# Part of Softhealer Technologies

{
    'name': 'Clinic Management System',
    'version': '1.0',
    'summary': 'Clinic Management System',
    'sequence': 1,
    'description': """"
        A Clinic Management System is a comprehensive software solution designed to streamline the day-to-day operations of medical clinics. It helps manage patient records, appointments, billing, prescriptions, and inventory with ease and accuracy. The system improves efficiency, reduces paperwork, and enhances the overall patient experience.
    """,
    'category': 'Clinic Management System',
    'website': 'https://softhealer.com',

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base','web','account','sale', 'crm', 'hr', 'hr_contract', 'mail', 'portal'],

    'data': [
        # groups
        'security/res_groups.xml',
        
        # security
        'security/ir.model.access.csv',
        
        # date
        'data/apt_sequence.xml',
        'data/sh_mail_template.xml',
        
        # report
        # 'report/sh_appointment_template.xml',
        # 'report/sh_reports.xml',
        
        # wizard
        'wizard/sh_appointment_template.xml',
        
        # views
        'views/sh_allergies_view.xml',
        'views/sh_chronic_condition_view.xml',
        'views/sh_disease_category_view.xml',
        'views/sh_disease_view.xml',
        'views/sh_life_style_factor_view.xml',
        'views/sh_medicine_type_view.xml',
        'views/sh_mental_health_problem_view.xml',
        'views/sh_symptom_view.xml',
        'views/res_partner_view.xml',
        'views/hr_employee_view.xml',
        'views/product_template_view.xml',
        'views/sh_medicine_view.xml',
        'views/hr_job_view.xml',
        'views/hr_department_view.xml',
        'views/resource_calendar_view.xml',
        'views/sh_slots_view.xml',
        'views/res_config_settings_view.xml',
        'views/sh_appointment_view.xml',
        'views/report_appointment.xml',
        'views/portal_templates.xml',
        'wizard/sh_reports.xml',
        
        # menuitem
        'views/sh_clinic_menuitems.xml',
    ],
    'assets': {
        'web.assets_frontend': [
                'sh_clinic_mgmt/static/src/js/portal.js',
            ],
    },
        
    'installable': True,
    'application': True,
    
    'license': 'LGPL-3',
    
    
}

