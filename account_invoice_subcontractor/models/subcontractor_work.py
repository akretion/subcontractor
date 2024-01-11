# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
from collections import OrderedDict
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import first

_logger = logging.getLogger(__name__)

INVOICE_STATE = [
    ("draft", "Draft"),
    ("posted", "Posted"),
    ("paid", "Paid"),
    ("cancel", "Cancelled"),
]


class SubcontractorWork(models.Model):
    _name = "subcontractor.work"
    _description = "subcontractor work"
    _order = "id desc"

    @api.model
    def _get_subcontractor_type(self):
        return self.env["hr.employee"]._get_subcontractor_type()

    name = fields.Char(related="invoice_line_id.name", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    invoice_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Invoice Line",
        required=True,
        ondelete="cascade",
        copy=False,
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        related="invoice_line_id.move_id",
        string="Invoice",
        store=True,
    )
    # TODO rename invoice_date like in account.move
    invoice_date = fields.Date(
        related="invoice_line_id.move_id.invoice_date",
        string="Invoice Date",
        store=True,
    )
    supplier_invoice_line_id = fields.Many2one(
        comodel_name="account.move.line", string="Supplier Invoice Line", copy=False
    )
    supplier_invoice_id = fields.Many2one(
        comodel_name="account.move",
        related="supplier_invoice_line_id.move_id",
        string="Supplier Invoice",
        store=True,
    )
    date_supplier_invoice = fields.Date(
        related="supplier_invoice_line_id.move_id.invoice_date",
        string="Supplier Invoice Date",
        store=True,
    )
    quantity = fields.Float(digits="Product Unit of Measure")
    sale_price_unit = fields.Float(
        compute="_compute_price", digits="Account", store=True
    )
    cost_price_unit = fields.Float(
        compute="_compute_price", digits="Account", store=True
    )
    cost_price = fields.Float(compute="_compute_price", digits="Account", store=True)
    sale_price = fields.Float(compute="_compute_price", digits="Account", store=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="invoice_line_id.company_id",
        string="Company",
        store=True,
    )
    customer_id = fields.Many2one(
        comodel_name="res.partner",
        related="company_id.partner_id",
        string="Customer",
        store=True,
    )
    end_customer_id = fields.Many2one(
        comodel_name="res.partner",
        related="invoice_id.partner_id",
        store=True,
        string="Customer(end)",
    )
    subcontractor_invoice_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Subcontractor Invoice Line",
        copy=False,
    )
    subcontractor_company_id = fields.Many2one(
        comodel_name="res.company",
        related="employee_id.subcontractor_company_id",
        store=True,
        string="Subcontractor Company",
    )
    subcontractor_state = fields.Selection(
        compute="_compute_state", selection=INVOICE_STATE, store=True, compute_sudo=True
    )
    subcontractor_type = fields.Selection(
        string="Subcontractor Type", selection="_get_subcontractor_type"
    )
    state = fields.Selection(
        compute="_compute_state",
        selection=INVOICE_STATE,
        store=True,
        default="draft",
        compute_sudo=True,
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        related="invoice_line_id.product_uom_id",
        store=True,
        string="Unit",
    )
    # same_fiscalyear = fields.Boolean()
    # # We keep the data here
    # # compute='_check_same_fiscalyear',
    # # store=True,
    # # compute_sudo=True)
    # min_fiscalyear = fields.Char()
    # # compute='_check_same_fiscalyear',
    # # store=True,
    # # compute_sudo=True)

    # #
    # # @api.depends(
    # #     'invoice_line_id.invoice_id.date_invoice',
    # #     'supplier_invoice_line_id.invoice_id.date_invoice')
    # # def _check_same_fiscalyear(self):
    # #     fyo = lf.env['account.fiscalyear']
    # #     for sub in self:
    # #         invoice_year_id = fyo.find(
    # #             sub.invoice_line_id.invoice_id.date_invoice)
    # #         supplier_invoice_year_id = fyo.find(
    # #             sub.supplier_invoice_line_id.invoice_id.date_invoice)
    # #         sub.same_fiscalyear = invoice_year_id == supplier_invoice_year_id
    # #         invoice_year = fyo.browse(invoice_year_id)
    # #         supplier_invoice_year = fyo.browse(supplier_invoice_year_id)
    # #         if invoice_year and supplier_invoice_year:
    # #             sub.min_fiscalyear = min(
    # #                 invoice_year.name,
    # #                 supplier_invoice_year.name)
    # #         else:
    # #             sub.min_fiscalyear = max(
    # #                 invoice_year.name,
    # #                 supplier_invoice_year.name)

    def _get_commission_rate(self):
        company = self.invoice_line_id.company_id or self.env.company
        return company._get_commission_rate()

    @api.depends(
        "employee_id",
        "invoice_line_id",
        "invoice_line_id.product_id",
        "invoice_line_id.price_unit",
        "invoice_line_id.discount",
        "invoice_line_id.quantity",
        "quantity",
    )
    def _compute_price(self):
        for work in self:
            line = work.invoice_line_id
            sale_price_unit = line.price_unit * (1 - line.discount / 100.0)
            rate = 1
            if not work.invoice_line_id.product_id.no_commission:
                rate -= work._get_commission_rate()
            cost_price_unit = sale_price_unit * rate
            work.sale_price_unit = sale_price_unit
            work.cost_price_unit = cost_price_unit
            work.cost_price = work.quantity * work.cost_price_unit
            work.sale_price = work.quantity * work.sale_price_unit

    @api.onchange("employee_id")
    def employee_id_onchange(self):
        self.ensure_one()
        if self.employee_id:
            self.subcontractor_type = self.employee_id.subcontractor_type
            line = self.invoice_line_id
            # TODO find a good way to get the right qty
            self.quantity = line.quantity

    @api.depends(
        "invoice_line_id",
        "invoice_line_id.move_id.state",
        "invoice_line_id.move_id.payment_state",
        "supplier_invoice_line_id",
        "supplier_invoice_line_id.move_id.state",
        "supplier_invoice_line_id.move_id.payment_state",
    )
    def _compute_state(self):
        def get_state(move):
            if move.payment_state == "paid":
                return "paid"
            else:
                return move.state

        for work in self:
            if work.invoice_line_id:
                work.state = get_state(work.invoice_id)
            if work.supplier_invoice_line_id:
                work.subcontractor_state = get_state(work.supplier_invoice_id)

    def check(self, work_type=False):
        partner_id = self[0].customer_id.id
        worktype = self[0].subcontractor_type
        for work in self:
            dest_invoice_company = work._get_dest_invoice_company()
            if dest_invoice_company not in self.env.companies:
                raise UserError(
                    _(
                        "You can't generate an invoice for a company you have no access : %s"
                        % dest_invoice_company.name
                    )
                )
            if partner_id != work.customer_id.id:
                raise UserError(_("All the work should belong to the same supplier"))
            elif work.supplier_invoice_line_id:
                raise UserError(_("This work has been already invoiced!"))
            elif work.state not in ("posted", "paid"):
                raise UserError(
                    _("Only works with the state 'posted' or 'paid' can be invoiced")
                )
            elif worktype != work.subcontractor_type:
                raise UserError(
                    _("All the work should have the same subcontractor type")
                )
            elif work_type and work.subcontractor_type != work_type:
                raise UserError(
                    _("You can invoice on only the %s subcontractors" % work_type)
                )

    @api.model
    def _prepare_invoice(self):
        self.ensure_one()
        # the source invoice is always from customer, out_invoice or out_refund
        # but, depending on the subcontractor type, we want to create :
        # 1. For internal : the same type of invoice on the subcontractor company side
        # Then the supplier invoice/refund will be created with intercompant invoice
        # module.
        # 2. For external : directly create a supplier invoice/refund
        orig_invoice = self.sudo().invoice_id
        if orig_invoice.move_type not in ("out_invoice", "out_refund"):
            raise UserError(
                _(
                    "You can only invoice the subcontractors on a customer invoice/refund"
                )
            )
        company = self._get_dest_invoice_company()
        if self.subcontractor_type == "internal":
            invoice_type = orig_invoice.move_type
            journal_type = "sale"
            partner = self.customer_id
        elif self.subcontractor_type == "external":
            invoice_type = (
                orig_invoice.move_type == "out_invoice" and "in_invoice" or "in_refund"
            )
            journal_type = "purchase"
            partner = self.employee_id._get_employee_invoice_partner()
        if invoice_type in ["out_invoice", "out_refund"]:
            user = self.env["res.users"].search(
                [("company_id", "=", company.id)], limit=1
            )
        elif invoice_type in ["in_invoice", "in_refund"]:
            user = self.employee_id.user_id
        #        self = self.with_company(dest_invoice_company)
        journal = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", journal_type)], limit=1
        )
        if not journal:
            raise UserError(
                _('Please define %s journal for this company: "%s" (id:%d).')
                % (journal_type, company.name, company.id)
            )
        invoice_vals = {"partner_id": partner.id, "move_type": invoice_type}
        invoice_vals = self.env["account.move"].play_onchanges(
            invoice_vals, ["partner_id"]
        )
        original_invoice_date = orig_invoice.invoice_date
        last_invoices = self.env["account.move"].search(
            [
                ("move_type", "=", invoice_type),
                ("company_id", "=", company.id),
                ("invoice_date", ">", original_invoice_date),
                ("name", "!=", False),
            ],
            order="invoice_date desc",
        )
        if not last_invoices:
            invoice_date = original_invoice_date
        else:
            invoice_date = last_invoices[0].invoice_date
        invoice_vals.update(
            {
                "invoice_date": invoice_date,
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_line_ids": [(6, 0, [])],
                "currency_id": company.currency_id.id,
                "user_id": user.id,
            }
        )
        if invoice_type in ["out_invoice", "out_refund"]:
            invoice_vals["origin_customer_invoice_id"] = orig_invoice.id
        elif invoice_type in ["in_invoice", "in_refund"]:
            invoice_vals["customer_invoice_id"] = orig_invoice.id
        return invoice_vals

    @api.model
    def _prepare_invoice_line(self, invoice):
        self.ensure_one()
        invoice_line_obj = self.env["account.move.line"]
        line_vals = {
            "product_id": self.sudo().invoice_line_id.product_id.id,
            "quantity": self.quantity,
            "name": "Client final {} :{}".format(self.end_customer_id.name, self.name),
            "price_unit": self.cost_price_unit,
            "move_id": invoice.id,
            "subcontractor_work_invoiced_id": self.id,
            "product_uom_id": self.uom_id.id,
        }
        if hasattr(self.sudo().invoice_line_id, "start_date") and hasattr(
            self.sudo().invoice_line_id, "end_date"
        ):
            line_vals.update(
                {
                    "start_date": self.sudo().invoice_line_id.start_date,
                    "end_date": self.sudo().invoice_line_id.end_date,
                }
            )
        onchange_vals = invoice_line_obj.play_onchanges(line_vals, ["product_id"])
        line_vals.update(onchange_vals)
        return line_vals

    def _get_subcontractor_invoicing_group(self):
        groups = OrderedDict()
        for sub in self.sorted("invoice_date"):
            if sub.subcontractor_type == "internal":
                key = (sub.employee_id.id, sub.invoice_id.id)
            elif sub.subcontractor_type == "external":
                key = (sub.employee_id.id, False)
            if key not in groups:
                groups[key] = self.env["subcontractor.work"]
            groups[key] |= sub
        return groups

    def _get_dest_invoice_company(self):
        self.ensure_one()
        if self.subcontractor_type == "internal":
            company = self.subcontractor_company_id
        elif self.subcontractor_type == "external":
            company = self.sudo().invoice_id.company_id
        else:
            raise NotImplementedError
        return company

    def invoice_from_work(self):
        # group subcontractor by invoice : internal sub should produce one invoice
        # per (employee/original_invoice_id) and external sub should produce one
        # invoice per employee
        invoices = self.env["account.move"]
        grouped_subcontractors = self._get_subcontractor_invoicing_group()
        invoice_obj = self.env["account.move"]
        for subcontractor_works in grouped_subcontractors.values():
            invoice_data_list = []
            # since subcontractor are grouped by dest invoice, they all should
            # be consitent for finding the dest company or generating the dest invoice
            # vals
            first_work = first(subcontractor_works)
            company = first_work._get_dest_invoice_company()
            invoice_vals = first_work.with_company(company)._prepare_invoice()
            invoice = invoice_obj.with_company(company).create(invoice_vals)
            invoices |= invoice
            for work in subcontractor_works.with_company(company):
                inv_line_data = work._prepare_invoice_line(invoice)
                invoice_data_list.append((0, 0, inv_line_data))
            invoice.write({"invoice_line_ids": invoice_data_list})
        return invoices

    def _scheduler_action_subcontractor_invoice_create(self):
        date_filter = date.today() - timedelta(days=7)
        subcontractors = self.env["hr.employee"].search(
            [
                ("subcontractor_type", "=", "internal"),
                ("subcontractor_company_id", "!=", False),
            ]
        )
        # Need to search on all subcontractor work
        # because of the filter on date invoice
        all_works = self.search(
            [
                ("invoice_id.invoice_date", "<=", date_filter),
                ("subcontractor_invoice_line_id", "=", False),
                ("subcontractor_type", "=", "internal"),
                ("state", "in", ["posted", "paid"]),
            ],
        )
        for subcontractor in subcontractors:
            dest_company = subcontractor.subcontractor_company_id
            user = subcontractor.user_id
            #            # TOFIX
            #            old_company = False
            #            if user.company_id != dest_company:
            #                if dest_company.id in user.company_ids.ids:
            #                    old_company = user.company_id
            #                    user.company_id = subcontractor.subcontractor_company_id
            #                else:
            #                    user = self.env["res.users"].search(
            #                        [("company_id", "=", dest_company.id)], limit=1
            #                    )
            subcontractor_works = (
                self.with_user(user)
                .with_company(dest_company)
                .search(
                    [
                        ("id", "in", all_works.ids),
                        ("employee_id", "=", subcontractor.id),
                    ],
                )
            )
            _logger.info(
                "%s lines found for subcontractor %s"
                % (subcontractor_works.ids, subcontractor.name)
            )
            invoices = subcontractor_works.invoice_from_work()
            for invoice in invoices:
                invoice.action_post()
        #            if old_company:
        #                user.company_id = old_company.id
        return True

    def write(self, vals):
        already_invoiced = self.env["subcontractor.work"]
        if vals.get("subcontractor_invoice_line_id"):
            already_invoiced = self.filtered(lambda s: s.subcontractor_invoice_line_id)
        if vals.get("supplier_invoice_line_id"):
            already_invoiced = self.filtered(lambda s: s.supplier_invoice_line_id)
        if any(field in vals for field in ["employee_id", "quantity"]):
            already_invoiced = self.filtered(
                lambda s: s.subcontractor_invoice_line_id or s.supplier_invoice_line_id
            )
        if already_invoiced:
            raise UserError(
                _(
                    "You can't edit a subcontractor already invoiced %s"
                    % already_invoiced.ids
                )
            )
        return super().write(vals)

    def unlink(self):
        already_invoiced = self.filtered(
            lambda s: s.subcontractor_invoice_line_id or s.supplier_invoice_line_id
        )
        if already_invoiced:
            raise UserError(
                _(
                    "You can't delete a subcontractor already invoiced %s"
                    % already_invoiced.ids
                )
            )
        return super().unlink()

    def action_post(self):
        invalid_invoice = self.filtered(lambda m: m.invalid_work_amount)
        if invalid_invoice:
            raise UserError(
                _("You can't validate an invoice with invalid work amount!")
            )
        return super().action_post()
