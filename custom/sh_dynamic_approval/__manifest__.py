# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

{
    'name': 'Dynamic Approval Engine',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Configurable multi-model dynamic approval workflow engine',
    'description': """
Dynamic Approval Engine
=======================
Centralized configurable approval workflow for standard and custom Odoo models.
Supports model/domain based rules, create/write/manual triggers, multi-level
approval, delegation, escalation, audit logs, email notifications, dashboards,
bulk approval, and multi-company isolation.
""",
    'author': 'Softhealer Technologies',
    'website': 'https://www.softhealer.com',
    'support': 'support@softhealer.com',
    'license': 'OPL-1',
    'depends': [
        'base',
        'web',
        'mail',
        'hr',
        'hr_holidays',
    ],
    'data': [
        'security/sh_dynamic_approval_security.xml',
        'security/ir.model.access.csv',
        'data/sh_dynamic_approval_mail_templates.xml',
        'data/sh_dynamic_approval_actions.xml',
        'data/sh_dynamic_approval_cron.xml',
        'views/sh_approval_type_views.xml',
        'views/sh_approval_request_views.xml',
        'views/sh_approval_dashboard_views.xml',
        'views/sh_dynamic_approval_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sh_dynamic_approval/static/src/js/sh_disable_relational_create.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
