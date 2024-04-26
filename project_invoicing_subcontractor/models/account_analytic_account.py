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
            not_paid_lines = move_lines - paid_lines
            supplier_not_paid = not_paid_lines.filtered(
                lambda line: line.amount_currency > 0.0
            )
            available_amount -= sum(supplier_not_paid.mapped("amount_currency"))
            account.prepaid_total_amount = total_amount
            # this one is used for display/info, so we show what is really available
            # as if all supplier invoices were paid.
            account.prepaid_available_amount = available_amount
            # Keep available_amount without to_pay supplier invoices neither ongoing
            # supplier invoices because it is used to make them to pay.
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
