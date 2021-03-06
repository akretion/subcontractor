# © 2015 Akretion
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    _map_type = {
        "in_invoice": "supplier_invoice_line_id",
        "out_invoice": "subcontractor_invoice_line_id",
    }

    subcontracted = fields.Boolean()
    subcontractor_work_ids = fields.One2many(
        "subcontractor.work", "invoice_line_id", string="Subcontractor Work"
    )
    subcontractor_work_invoiced_id = fields.Many2one(
        "subcontractor.work",
        compute="_get_work_invoiced",
        inverse="_set_work_invoiced",
        string="Invoiced Work",
        store=True,
        _prefetch=False,
    )
    invalid_work_amount = fields.Boolean(
        compute="_is_work_amount_invalid", string="Work Amount Invalid", store=True
    )
    subcontractors = fields.Char(string="Sub C.", compute="_compute_subcontractors")

    @api.multi
    def _compute_subcontractors(self):
        for rec in self:
            rec.subcontractors = " / ".join(
                list({x.employee_id.name[0:4] for x in rec.subcontractor_work_ids})
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        super(AccountInvoiceLine, self)._onchange_product_id()
        for rec in self:
            rec.subcontracted = rec.product_id.subcontracted

    @api.depends("invoice_id", "invoice_id.type")
    @api.multi
    def _get_work_invoiced(self):
        for line in self:
            field = self._map_type.get(line.invoice_id.type, False)
            if field:
                work_obj = self.env["subcontractor.work"]
                work = work_obj.search([[field, "=", line.id]])
                line.subcontractor_work_invoiced_id = work.id

    @api.multi
    def _set_work_invoiced(self):
        for line in self:
            work = line.subcontractor_work_invoiced_id
            if work:
                field = self._map_type.get(line.invoice_id.type, False)
                if field:
                    work.sudo().write({field: line.id})

    @api.depends(
        "invoice_id",
        "invoice_id.type",
        "invoice_id.company_id",
        "invoice_id.partner_id",
        "subcontractor_work_invoiced_id",
        "subcontractor_work_invoiced_id.cost_price",
        "price_subtotal",
        "subcontracted",
    )
    @api.multi
    def _is_work_amount_invalid(self):
        for line in self:
            if line.invoice_id.type in ["out_invoice", "in_invoice"]:
                if line.subcontracted:
                    if line.invoice_id.type == "in_invoice":
                        line.invalid_work_amount = line._check_in_invoice_amount()
                    else:
                        line.invalid_work_amount = line._check_out_invoice_amount()

    def _check_in_invoice_amount(self):
        return (
            abs(self.subcontractor_work_invoiced_id.cost_price - self.price_subtotal)
            > 0.1
        )

    def _check_out_invoice_amount(self):
        # TODO FIXME
        if self.invoice_id.company_id.id != 1:
            # this mean Akretion
            if self.invoice_id.partner_id.id == 1:
                return (
                    abs(
                        self.subcontractor_work_invoiced_id.cost_price
                        - self.price_subtotal
                    )
                    > 0.1
                )
        else:
            subtotal = sum(self.subcontractor_work_ids.mapped("sale_price"))
            return abs(subtotal - self.price_subtotal) > 0.01


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    to_pay = fields.Boolean(compute="_get_to_pay", store=True, compute_sudo=True)
    invalid_work_amount = fields.Boolean(compute="_is_work_amount_valid", store=True)

    @api.depends(
        "invoice_line_ids",
        "invoice_line_ids.subcontractor_work_invoiced_id",
        "invoice_line_ids.subcontractor_work_invoiced_id.state",
    )
    @api.multi
    def _get_to_pay(self):
        for invoice in self:
            if invoice.type == "in_invoice":
                if invoice.state == "paid":
                    invoice.to_pay = False
                else:
                    invoice.to_pay = all(
                        [
                            line.subcontractor_work_invoiced_id.state == "paid"
                            for line in invoice.invoice_line_ids
                        ]
                    )

    @api.depends("invoice_line_ids", "invoice_line_ids.invalid_work_amount")
    @api.multi
    def _is_work_amount_valid(self):
        for invoice in self:
            invoice.invalid_work_amount = any(
                [line.invalid_work_amount for line in invoice.invoice_line_ids]
            )

    @api.model
    def _prepare_invoice_line_data(
        self,
        dest_invoice,
        dest_inv_type,
        dest_company,
        src_line,
        src_company_partner_id,
    ):
        res = super()._prepare_invoice_line_data(
            dest_invoice, dest_inv_type, dest_company, src_line, src_company_partner_id
        )
        res[
            "subcontractor_work_invoiced_id"
        ] = src_line.subcontractor_work_invoiced_id.id
        return res
