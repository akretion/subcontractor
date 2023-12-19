# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    is_prepaid_account = fields.Boolean(
        help="These accounts are then selectable on product and used to sell work in "
        "advance to customers and put the revenue in the advanced revenue account"
        " and then transfer it to income account only when the subontractor "
        "invoices are generated."
    )
