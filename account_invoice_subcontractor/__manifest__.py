# © 2015 Akretion
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Account Invoice Subcontractor",
    "version": "14.0.0.0.2",
    "category": "Generic Modules/Others",
    "license": "AGPL-3",
    "author": "Akretion",
    "website": "https://github.com/akretion/subcontractor",
    "depends": [
        "hr",
        "account_invoice_inter_company",
        "onchange_helper",
        "sale",
    ],
    "data": [
        "data/cron_data.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/hr_view.xml",
        "views/subcontractor_work_view.xml",
        "views/invoice_view.xml",
        "wizard/subcontractor_invoice_work_view.xml",
        "views/product_view.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "installable": True,
}
