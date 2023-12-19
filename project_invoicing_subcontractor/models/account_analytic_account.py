# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    available_amount = fields.Monetary(compute="_compute_available_amount")
    account_move_line_ids = fields.One2many("account.move.line", "analytic_account_id")

    @api.depends("account_move_line_ids.prepaid_is_paid")
    def _compute_available_amount(self):
        for account in self:
            account_amounts = self.env["account.move.line"].read_group(
                [
                    ("analytic_account_id", "=", account.id),
                    ("prepaid_is_paid", "=", True),
                ],
                ["analytic_account_id", "amount_currency"],
                ["analytic_account_id"],
            )
            account.available_amount = -(
                account_amounts and account_amounts[0]["amount_currency"] or 0.0
            )
