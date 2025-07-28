# -*- coding: utf-8 -*-
{
    'name': "Ticket Support",

    'summary': "Support and Manage the Ticket",

    'description': """
Long description of module's purpose
    """,

    'author': "SoftHealer",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','web' , 'mail','contacts' , 'account'],

    # always loaded
    "data": [
        "security/ticket_security.xml",
        "security/ir.model.access.csv",
        "views/support_ticket_views.xml",
        "views/crone.xml",
        "views/Mass Action_views.xml",
        "views/res_partner_views.xml",
        "views/ticket_sequence.xml"
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

