# Copyright 2019-2020 Akretion France (http://www.akretion.com/)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    "name": "Contract Invoice Project",
    "version": "16.0.1.0.0",
    "category": "Contract Management",
    "author": "Akretion, Odoo Community Association (OCA)",
    "maintainers": ["florian-dacosta"],
    "website": "https://github.com/akretion/subcontractor",
    "depends": [
        "account_move_line_project",
        "contract",
    ],
    "data": ["views/contract_contract.xml"],
    "license": "AGPL-3",
    "installable": True,
    "auto_install": True,
}
