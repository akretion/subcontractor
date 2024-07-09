# Copyright 2024 Akretion (https://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Project Budget Subcontractor",
    "summary": "Add budget to projects",
    "version": "14.0.1.0.0",
    "development_status": "Alpha",
    "category": "Uncategorized",
    "website": "https://github.com/akretion/subcontractor",
    "author": " Akretion",
    "license": "AGPL-3",
    "depends": [
        "project_invoicing_subcontractor",
        "project_timeline",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_view.xml",
        "views/res_partner_view.xml",
        "views/project_project_view.xml",
        "views/project_budget_view.xml",
    ],
    "auto_install": True,
}
