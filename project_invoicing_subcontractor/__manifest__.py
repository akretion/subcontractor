# -*- coding: utf-8 -*-
# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

{
    'name': 'project_invoicing_subcontractor',
    'version': '10.0.0.0.1',
    'author': 'Akretion',
    'website': 'www.akretion.com',
    'license': 'AGPL-3',
    'category': 'Generic Modules',
    'summary': """Generate the subcontractor work automatically
                  when creating an invoice from the project invoicing menu
               """,
    'depends': [
        'hr_timesheet_task',
        'account_invoice_subcontractor',
    ],
    'data': [
        'wizards/subcontractor_timesheet_invoice_view.xml',
        'views/menu.xml',
        'views/hr_timesheet_view.xml',
    ],
    'installable': True,
}
