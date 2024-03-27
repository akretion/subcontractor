# © 2015 Akretion
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    _map_type = {
        "in_invoice": "supplier_invoice_line_id",
        "out_invoice": "subcontractor_invoice_line_id",
        "in_refund": "supplier_invoice_line_id",
        "out_refund": "subcontractor_invoice_line_id",
    }

    subcontracted = fields.Boolean()
    subcontractor_work_ids = fields.One2many(
        "subcontractor.work", "invoice_line_id", string="Subcontractor Work", copy=True
    )
    subcontractor_work_invoiced_id = fields.Many2one(
        "subcontractor.work",
        compute="_compute_subcontractor_work_invoiced_id",
        inverse="_inverse_subcontractor_work_invoiced_id",
        string="Invoiced Work",
        store=True,
    )
    invalid_work_amount = fields.Boolean(
        compute="_compute_invalid_work_amount", string="Work Amount Invalid", store=True
    )
    subcontractors = fields.Char(string="Sub C.", compute="_compute_subcontractors")

    def _compute_subcontractors(self):
        for rec in self:
            rec.subcontractors = " / ".join(
                list({x.employee_id.name[0:4] for x in rec.subcontractor_work_ids})
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        super()._onchange_product_id()
        for rec in self:
            rec.subcontracted = rec.product_id.subcontracted

    @api.depends("move_id", "move_id.move_type")
    def _compute_subcontractor_work_invoiced_id(self):
        for line in self:
            field = self._map_type.get(line.move_id.move_type, False)
            if field:
                work_obj = self.env["subcontractor.work"]
                work = work_obj.search([[field, "=", line.id]])
                if work:
                    line.subcontractor_work_invoiced_id = work.id

    def _inverse_subcontractor_work_invoiced_id(self):
        for line in self:
            work = line.subcontractor_work_invoiced_id
            if work:
                field = self._map_type.get(line.move_id.move_type, False)
                if field:
                    work.sudo().write({field: line.id})

    @api.depends(
        "move_id",
        "move_id.move_type",
        "move_id.company_id",
        "move_id.partner_id",
        "subcontractor_work_invoiced_id",
        "subcontractor_work_invoiced_id.cost_price",
        "subcontractor_work_ids",
        "subcontractor_work_ids.sale_price",
        "price_subtotal",
        "subcontracted",
    )
    def _compute_invalid_work_amount(self):
        for line in self:
            if line.subcontracted:
                if line.move_id.move_type in ["in_invoice", "in_refund"]:
                    line.invalid_work_amount = line._check_in_invoice_amount()
                else:
                    line.invalid_work_amount = line._check_out_invoice_amount()
            else:
                if line.subcontractor_work_ids:
                    line.invalid_work_amount = line.price_subtotal
                else:
                    line.invalid_work_amount = False

    def _check_in_invoice_amount(self):
        return (
            abs(self.subcontractor_work_invoiced_id.cost_price - self.price_subtotal)
            > 0.1
        )

    def _check_out_invoice_amount(self):
        # TODO FIXME
        if self.move_id.company_id.id != 1:
            # this mean Akretion
            if self.move_id.partner_id.id == 1:
                return (
                    abs(
                        self.subcontractor_work_invoiced_id.cost_price
                        - self.price_subtotal
                    )
                    > 0.1
                )
        else:
            subtotal = sum(self.subcontractor_work_ids.mapped("sale_price"))
            # we use a bigger diff to avoid issue with rounding
            return abs(subtotal - self.price_subtotal) > 5

    @api.model
    def _prepare_account_move_line(self, dest_invoice, dest_company, form=False):
        res = super()._prepare_account_move_line(dest_invoice, dest_company, form=form)
        res["subcontractor_work_invoiced_id"] = self.subcontractor_work_invoiced_id.id
        return res

    def edit_subcontractor(self):
        view = {
            "name": ("Details"),
            "view_type": "form",
            "view_mode": "form",
            "res_model": "account.move.line",
            "view_id": self.env.ref(
                "account_invoice_subcontractor.view_move_line_subcontractor_form"
            ).id,
            "type": "ir.actions.act_window",
            "target": "new",
            "res_id": self.id,
        }
        return view

    @api.onchange("quantity")
    def _onchange_quantity(self):
        for line in self:
            if len(line.subcontractor_work_ids) == 1:
                line.subcontractor_work_ids.quantity = line.quantity


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
