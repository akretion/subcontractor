# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    available_amount = fields.Monetary(compute="_compute_prepaid_amount")
    prepaid_total_amount = fields.Monetary(compute="_compute_prepaid_amount")
    prepaid_available_amount = fields.Monetary(compute="_compute_prepaid_amount")
    account_move_line_ids = fields.One2many("account.move.line", "analytic_account_id")

    @api.depends("account_move_line_ids.prepaid_is_paid")
    def _compute_prepaid_amount(self):
        for account in self:
            move_lines, paid_lines = account._prepaid_move_lines()
            total_amount = -sum(move_lines.mapped("amount_currency")) or 0.0
            available_amount = -sum(paid_lines.mapped("amount_currency")) or 0.0
            account.prepaid_total_amount = total_amount
            account.prepaid_available_amount = available_amount
            # Keep available_amount without to_pay supplier invoices
            account.available_amount = (
                -sum(
                    move_lines.filtered(lambda m: m.prepaid_is_paid).mapped(
                        "amount_currency"
                    )
                )
                or 0.0
            )

    def _prepaid_move_lines(self):
        self.ensure_one()
        move_lines = self.env["account.move.line"].search(
            [
                ("analytic_account_id", "=", self.id),
                ("account_id.is_prepaid_account", "=", True),
            ],
        )
        paid_lines = move_lines.filtered(
            lambda m: m.prepaid_is_paid
            or (
                m.move_id.supplier_invoice_ids
                and all(
                    [
                        x.to_pay and x.payment_state != "paid"
                        for x in m.move_id.supplier_invoice_ids
                    ]
                )
            )
        )
        return move_lines, paid_lines
