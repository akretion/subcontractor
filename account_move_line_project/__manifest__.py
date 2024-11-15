# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Account Move Line Project",
    "version": "16.0.1.0.0",
    "category": "Accounting",
    "summary": "Add project on account move line",
    "author": "Akretion,Odoo Community Association (OCA)",
    "website": "https://github.com/akretion/subcontractor",
    "license": "AGPL-3",
    "depends": [
        "account",
        "project",
    ],
    "data": [
        "security/security.xml",
        "views/account_move.xml",
        "views/account_move_line.xml",
    ],
    "installable": True,
}
