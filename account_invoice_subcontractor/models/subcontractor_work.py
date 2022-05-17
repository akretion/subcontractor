# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
        readonly=True,
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
        readonly=True,
        store=True,
    )
    customer_id = fields.Many2one(
        comodel_name="res.partner",
        related="company_id.partner_id",
        readonly=True,
        string="Customer",
        store=True,
    )
    end_customer_id = fields.Many2one(
        comodel_name="res.partner",
        related="invoice_id.partner_id",
        readonly=True,
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
        readonly=True,
        store=True,
        string="Subcontractor Company",
    )
    subcontractor_state = fields.Selection(
        compute="_get_state", selection=INVOICE_STATE, store=True, compute_sudo=True
    )
    subcontractor_type = fields.Selection(
        string="Subcontractor Type", selection="_get_subcontractor_type"
    )
    state = fields.Selection(
        compute="_get_state",
        selection=INVOICE_STATE,
        store=True,
        default="draft",
        compute_sudo=True,
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        related="invoice_line_id.product_uom_id",
        readonly=True,
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
                rate -= work.employee_id.commission_rate / 100.0
            cost_price_unit = sale_price_unit * rate
            work.sale_price_unit = sale_price_unit
            work.cost_price_unit = cost_price_unit
            work.cost_price = work.quantity * cost_price_unit
            work.sale_price = work.quantity * sale_price_unit

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
        "supplier_invoice_line_id",
        "supplier_invoice_line_id.move_id.state",
    )
    def _get_state(self):
        for work in self:
            if work.invoice_line_id:
                work.state = work.invoice_id.state
            if work.supplier_invoice_line_id:
                work.subcontractor_state = work.supplier_invoice_id.state

    def check(self, work_type=False):
        partner_id = self[0].customer_id.id
        worktype = self[0].subcontractor_type
        for work in self:
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
        journal_obj = self.env["account.journal"]
        inv_obj = self.env["account.move"]
        # the source invoice is always from customer, out_invoice or out_refund
        # but, depending on the subcontractor type, we want to create :
        # 1. For internal : the same type of invoice on the subcontractor company side
        # Then the supplier invoice/refund will be created with intercompant invoice
        # module.
        # 2. For external : directly create a supplier invoice/refund
        if self.sudo().invoice_id.move_type not in ("out_invoice", "out_refund"):
            raise UserError(
                "You can only invoice the subcontractors on a customer invoice/refund"
            )
        if self.subcontractor_type == "internal":
            invoice_type = self.sudo().invoice_id.move_type
        elif self.subcontractor_type == "external":
            invoice_type = (
                self.sudo().invoice_id.move_type == "out_invoice"
                and "in_invoice"
                or "in_refund"
            )
        if invoice_type in ["out_invoice", "out_refund"]:
            company = self.subcontractor_company_id
            journal_type = "sale"
            partner = self.customer_id
            user = self.env["res.users"].search(
                [("company_id", "=", company.id)], limit=1
            )
        elif invoice_type in ["in_invoice", "in_refund"]:
            company = self.invoice_id.company_id
            journal_type = "purchase"
            partner = self.employee_id.user_id.partner_id
            user = self.employee_id.user_id
        journal = journal_obj.search(
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
        original_invoice_date = self.sudo().invoice_id.invoice_date
        last_invoices = inv_obj.search(
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
            "discount": self.sudo().invoice_line_id.discount,
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

    def invoice_from_work(self):
        # works arrive here already sorted by employee and invoice (sort is done
        # by the cron or the wizard)? That's why the following code works and make
        # a good repartition of the work per invoice.
        # TODO MIGRATION It would be nice to refactore this to make this method work
        # properly independently of the order of the works.
        invoice_obj = self.env["account.move"]
        invoices = self.env["account.move"]
        current_employee_id = None
        current_invoice_id = None
        for work in self:
            # for internal works we want 1 invoice per employee/source invoice
            # for external we want one invoice per employee
            if current_employee_id != work.employee_id or (
                work.subcontractor_type == "internal"
                and current_invoice_id != work.invoice_id
            ):
                invoice_vals = work._prepare_invoice()
                invoice = invoice_obj.create(invoice_vals)
                current_employee_id = work.employee_id
                current_invoice_id = work.invoice_id
                invoices |= invoice
            inv_line_data = work._prepare_invoice_line(invoice)
            # Need sudo because odoo prefetch de work.invoice_id
            # and try to read fields on it and that makes access rules fail
            invoice.sudo().write({"invoice_line_ids": [(0, 0, inv_line_data)]})
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
            order="invoice_date",
        )
        for subcontractor in subcontractors:
            dest_company = subcontractor.subcontractor_company_id
            user = subcontractor.user_id
            # TOFIX
            old_company = False
            if user.company_id != dest_company:
                if dest_company.id in user.company_ids.ids:
                    old_company = user.company_id
                    user.company_id = subcontractor.subcontractor_company_id
                else:
                    user = self.env["res.users"].search(
                        [("company_id", "=", dest_company.id)], limit=1
                    )
            subcontractor_works = (
                self.with_user(user)
                .with_company(dest_company)
                .search(
                    [
                        ("id", "in", all_works.ids),
                        ("employee_id", "=", subcontractor.id),
                    ],
                    order="employee_id, invoice_date, invoice_id",
                )
            )
            _logger.info(
                "%s lines found for subcontractor %s"
                % (subcontractor_works.ids, subcontractor.name)
            )
            invoices = subcontractor_works.invoice_from_work()
            for invoice in invoices:
                invoice.action_post()
            if old_company:
                user.company_id = old_company.id
        return True
