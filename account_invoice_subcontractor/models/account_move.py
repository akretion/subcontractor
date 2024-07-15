# © 2015 Akretion
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = "account.move"

    to_pay = fields.Boolean(compute="_compute_to_pay", store=True, compute_sudo=True)
    invalid_work_amount = fields.Boolean(
        compute="_compute_invalid_work_amount", store=True
    )
    customer_invoice_ids = fields.Many2many(
        comodel_name="account.move",
        relation="customer_subcontractor_invoice_rel",
        column1="customer_invoice_id",
        column2="sub_invoice_id",
        string="Customer invoices",
        readonly=True,
    )
    subcontractor_invoice_ids = fields.Many2many(
        comodel_name="account.move",
        relation="customer_subcontractor_invoice_rel",
        column1="sub_invoice_id",
        column2="customer_invoice_id",
        string="Supplier invoices",
        readonly=True,
    )
    origin_customer_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Original customer invoice",
        readonly=True,
        prefetch=False,
    )

    @api.depends(
        "invoice_line_ids",
        "invoice_line_ids.subcontractor_work_invoiced_id",
        "invoice_line_ids.subcontractor_work_invoiced_id.state",
        "payment_state",
        "move_type",
    )
    def _compute_to_pay(self):
        for invoice in self:
            if invoice.move_type in ["in_invoice", "in_refund"]:
                if invoice.payment_state == "paid":
                    invoice.to_pay = False
                else:
                    invoice.to_pay = all(
                        [
                            line.subcontractor_work_invoiced_id.state == "paid"
                            for line in invoice.invoice_line_ids
                        ]
                    )

    @api.depends("invoice_line_ids", "invoice_line_ids.invalid_work_amount")
    def _compute_invalid_work_amount(self):
        for invoice in self:
            invoice.invalid_work_amount = any(
                [line.invalid_work_amount for line in invoice.invoice_line_ids]
            )

    def action_view_subcontractor_invoices(self):
        self.ensure_one()
        action = self.env.ref("account.action_move_in_invoice_type").sudo().read()[0]
        action["domain"] = [("id", "in", self.subcontractor_invoice_ids.ids)]
        action["context"] = {
            "default_move_type": "in_invoice",
            "move_type": "in_invoice",
            "journal_type": "sale",
            "active_test": False,
        }
        return action

    def action_view_customer_invoices(self):
        self.ensure_one()
        action = self.env.ref("account.action_move_out_invoice_type").sudo().read()[0]
        action["domain"] = [("id", "in", self.customer_invoice_ids.ids)]
        action["context"] = {
            "default_move_type": "out_invoice",
            "move_type": "out_invoice",
            "journal_type": "sale",
            "active_test": False,
        }
        return action

    def already_subcontracted(self):
        invoices = self.subcontractor_invoice_ids
        invoices |= self.sudo().search([("origin_customer_invoice_id", "in", self.ids)])
        return invoices and True or False

    def button_draft(self):
        if self.already_subcontracted():
            raise UserError(
                _("You can't set to draft an invoice already invoiced by subcontractor")
            )
        return super().button_draft()

    def button_cancel(self):
        if self.already_subcontracted():
            raise UserError(
                _("You can't cancel an invoice already invoiced by subcontractor")
            )
        return super().button_cancel()

    def action_post(self):
        invalid_invoice = self.filtered(lambda m: m.invalid_work_amount)
        if invalid_invoice:
            raise UserError(
                _("You can't validate an invoice with invalid work amount!")
            )
        precision = self.env["decimal.precision"].precision_get("Account")
        invalid_invoice = self.sudo().filtered(
            lambda m: m.auto_invoice_id
            and float_compare(
                m.amount_total,
                m.auto_invoice_id.amount_total,
                precision_digits=precision,
            )
        )
        if invalid_invoice:
            raise UserError(
                _(
                    "You can't validate an invoice that is not consistent with its "
                    "intercompany invoice."
                )
            )
        return super().action_post()

    def _prepare_invoice_data(self, dest_company):
        vals = super()._prepare_invoice_data(dest_company)
        vals["customer_invoice_ids"] = [(6, 0, self.origin_customer_invoice_id.ids)]
        return vals
