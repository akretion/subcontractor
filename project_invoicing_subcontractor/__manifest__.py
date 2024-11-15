# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

{
    "name": "project_invoicing_subcontractor",
    "version": "16.0.2.0.0",
    "author": "Akretion",
    "website": "https://github.com/akretion/subcontractor",
    "license": "AGPL-3",
    "category": "Generic Modules",
    "summary": """Generate the subcontractor work automatically
                  when creating an invoice from the project invoicing menu
               """,
    "depends": [
        "hr_timesheet_sheet",
        "account_invoice_subcontractor",
        "project_time_in_day",
        "account_move_line_project",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/subcontractor_timesheet_invoice_view.xml",
        "views/menu.xml",
        "views/account_invoice_view.xml",
        "views/hr_timesheet_view.xml",
        "views/project_view.xml",
        "views/hr_timesheet_sheet.xml",
        "views/project_invoice_typology.xml",
        "views/product_template.xml",
        "views/account_account.xml",
        "views/res_partner.xml",
        "wizards/res_config_settings.xml",
        "data/ir_cron.xml",
    ],
    "demo": [
        "demo/account_account.xml",
        "demo/product_product.xml",
        "demo/project_invoice_typology.xml",
        "demo/project_demo.xml",
    ],
    "installable": True,
}
