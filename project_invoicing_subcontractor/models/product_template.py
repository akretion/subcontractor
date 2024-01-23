# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    prepaid_revenue_account_id = fields.Many2one(
        "account.account",
        company_dependent=True,
        domain=[("is_prepaid_account", "=", True)],
        help="Configure a prepaid account only if this product is used to invoice stuff"
        " in advance.",
    )

    def _get_product_accounts(self):
        res = super()._get_product_accounts()
        res["prepaid"] = self.prepaid_revenue_account_id
        return res
