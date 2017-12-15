# coding: utf-8
# © 2015 Akretion
#   @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    'name': 'Account Invoice Subcontractor',
    'version': '10.0.0.0.1',
    'category': 'Generic Modules/Others',
    'license': 'AGPL-3',
    'author': 'Akretion',
    'website': 'http://www.akretion.com/',
    'depends': [
        'hr',
        'account_invoice_inter_company',
    ],
    'data': [
        'data/cron_data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'hr_view.xml',
        'subcontractor_work_view.xml',
        'invoice_view.xml',
        # 'wizard/subcontractor_invoice_work_view.xml',
        # 'wizard/supplier_invoice_work_view.xml',
        'product_view.xml',
    ],
    'installable': True,
}
