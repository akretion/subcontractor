# © 2015 Akretion
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

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
    )
    invalid_work_amount = fields.Boolean(
        compute="_is_work_amount_invalid", string="Work Amount Invalid", store=True
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
    def _get_work_invoiced(self):
        for line in self:
            field = self._map_type.get(line.move_id.move_type, False)
            if field:
                work_obj = self.env["subcontractor.work"]
                work = work_obj.search([[field, "=", line.id]])
                if work:
                    line.subcontractor_work_invoiced_id = work.id

    def _set_work_invoiced(self):
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
    def _is_work_amount_invalid(self):
        for line in self:
            if line.subcontracted:
                if line.move_id.move_type in ["in_invoice", "in_refund"]:
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
    def _prepare_account_move_line(self, dest_invoice, dest_company):
        res = super()._prepare_account_move_line(dest_invoice, dest_company)
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

    to_pay = fields.Boolean(compute="_get_to_pay", store=True, compute_sudo=True)
    invalid_work_amount = fields.Boolean(compute="_is_work_amount_valid", store=True)

    @api.depends(
        "invoice_line_ids",
        "invoice_line_ids.subcontractor_work_invoiced_id",
        "invoice_line_ids.subcontractor_work_invoiced_id.state",
    )
    def _get_to_pay(self):
        for invoice in self:
            if invoice.move_type == "in_invoice":
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
    def _is_work_amount_valid(self):
        for invoice in self:
            invoice.invalid_work_amount = any(
                [line.invalid_work_amount for line in invoice.invoice_line_ids]
            )

    @api.model
    def _refund_cleanup_lines(self, lines):
        result = super()._refund_cleanup_lines(lines)
        for i, line in enumerate(lines):
            if hasattr(line, "subcontractor_work_ids"):
                works = []
                for work in line.subcontractor_work_ids:
                    new_work = work.copy_data(
                        {
                            "supplier_invoice_id": False,
                            "invoice_line_id": False,
                            "supplier_invoice_line_id": False,
                            "subcontractor_invoice_line_id": False,
                        }
                    )[0]
                    works.append((0, 0, new_work))
                result[i][2]["subcontractor_work_ids"] = works
        return result
