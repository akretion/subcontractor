# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from collections import defaultdict

from odoo import _, api, exceptions, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    task_id = fields.Many2one("project.task")
    task_stage_id = fields.Many2one(
        "project.task.type", related="task_id.stage_id", store=True
    )
    timesheet_line_ids = fields.One2many(
        "account.analytic.line", "invoice_line_id", "Timesheet Line"
    )
    timesheet_error = fields.Char(compute="_compute_timesheet_qty", store=True)
    timesheet_qty = fields.Float(
        digits="Product Unit of Measure",
        compute="_compute_timesheet_qty",
        store=True,
    )
    task_invoiceable_days = fields.Float(
        related="task_id.invoiceable_days",
        digits="Product Unit of Measure",
        string="Task Days",
        help="Total days of the task, helper to check if you miss some timesheet",
    )
    prepaid_is_paid = fields.Boolean(compute="_compute_prepaid_is_paid", store=True)

    @api.depends(
        "account_id",
        "move_id.payment_state",
        "move_id.supplier_invoice_ids.payment_state",
        "move_id.move_type",
        "move_id.state",
    )
    def _compute_prepaid_is_paid(self):
        for line in self:
            if not line.account_id.is_prepaid_account:
                continue
            move = line.move_id
            if move.state in ("draft", "cancel"):
                line.prepaid_is_paid = False
            elif move.move_type == "out_refund":
                line.prepaid_is_paid = True
            elif move.move_type == "out_invoice":
                if move.payment_state in ("paid", "reversed"):
                    line.prepaid_is_paid = True
                else:
                    line.prepaid_is_paid = False
            elif move.supplier_invoice_ids:
                if all(
                    [
                        x.payment_state in ("paid", "reversed")
                        for x in move.supplier_invoice_ids
                    ]
                ):
                    line.prepaid_is_paid = True
                else:
                    line.prepaid_is_paid = False
            # OD to manage migration toward this system?
            else:
                line.prepaid_is_paid = True

    @api.depends(
        "timesheet_line_ids.discount", "timesheet_line_ids.unit_amount", "quantity"
    )
    def _compute_timesheet_qty(self):
        for record in self:
            record.timesheet_qty = (
                record.timesheet_line_ids._get_invoiceable_qty_with_unit(
                    record.product_uom_id
                )
            )
            if abs(record.timesheet_qty - record.quantity) > 0.001:
                record.timesheet_error = "⏰ %s" % record.timesheet_qty

    def open_task(self):
        self.ensure_one()
        action = self.env.ref("project.action_view_task").sudo().read()[0]
        action.update(
            {
                "res_id": self.task_id.id,
                "views": [x for x in action["views"] if x[1] == "form"],
            }
        )
        return action

    def _get_computed_account(self):
        if (
            self.move_id.move_type in ("out_refund", "out_invoice")
            and self.product_id.prepaid_revenue_account_id
        ):
            return self.product_id.prepaid_revenue_account_id
        else:
            return super()._get_computed_account()


class AccountMove(models.Model):
    _inherit = "account.move"

    prepaid_countdown_move_id = fields.Many2one("account.move")
    supplier_invoice_ids = fields.One2many("account.move", "prepaid_countdown_move_id")
    is_supplier_prepaid = fields.Boolean(
        compute="_compute_is_supplier_prepaid", store=True
    )
    enough_analytic_amount = fields.Boolean(
        help="This field indicates that the invoice can be paid because there is "
        "enough money in the linked analytic account."
    )
    customer_id = fields.Many2one(
        "res.partner", compute="_compute_customer_id", store=True
    )

    @api.depends("invoice_line_ids.analytic_account_id")
    def _compute_customer_id(self):
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            partner = move.invoice_line_ids.analytic_account_id.partner_id
            move.customer_id = len(partner) == 1 and partner.id or False

    @api.depends("move_type", "invoice_line_ids.product_id")
    def _compute_is_supplier_prepaid(self):
        for inv in self:
            if inv.move_type in ("in_invoice", "in_refund") and any(
                [
                    line.product_id.prepaid_revenue_account_id
                    for line in inv.invoice_line_ids
                ]
            ):
                inv.is_supplier_prepaid = True
            else:
                pass

    def action_view_subcontractor(self):
        self.ensure_one()
        action = (
            self.env.ref("account_invoice_subcontractor.action_subcontractor_work")
            .sudo()
            .read()[0]
        )
        if self.move_type in ["out_invoice", "out_refund"]:
            action["context"] = {
                "search_default_invoice_id": self.id,
                "search_default_subcontractor": 1,
            }
        elif self.move_type in ["in_invoice", "in_refund"]:
            action["context"] = {
                "search_default_supplier_invoice_id": self.id,
            }
        return action

    def action_view_analytic_line(self):
        self.ensure_one()
        action = self.env.ref("hr_timesheet.act_hr_timesheet_line").sudo().read()[0]
        if self.move_type in ["out_invoice", "out_refund"]:
            action["domain"] = [("invoice_id", "=", self.id)]
        elif self.move_type in ["in_invoice", "in_refund"]:
            action["domain"] = [
                (
                    "id",
                    "=",
                    self.invoice_line_ids.subcontractor_work_invoiced_id.timesheet_line_ids.ids,
                )
            ]
        return action

    def _move_autocomplete_invoice_lines_values(self):
        # Following code is in this method :
        #   if line.product_id and not line._cache.get('name'):
        #        line.name = line._get_computed_name()
        # it reset invoice_line name to defaut in case it is not in cache.
        # The reason to do this would be
        # "Furthermore, the product's label was missing on all invoice lines."
        # https://github.com/OCA/OCB/commit/7965c890c4e6f6562d265e1605fef3384b00316e
        # So to avoid issues I read the name before the supper to ensure it is in cache
        # That is really depressing...
        # TODO a PR to fix this should be done I guess, but I have not the motivation
        # right now...
        self.invoice_line_ids.mapped("name")
        return super()._move_autocomplete_invoice_lines_values()

    def _create_prepare_prepaid_move_vals(self):
        self.ensure_one()
        # TODO configure dedicated journal on company?
        vals = {
            "ref": _("prepaid countdown for %s") % self.name,
            "date": self.date,
            "currency_id": self.currency_id.id,
            "company_id": self.company_id.id,
            "move_type": "entry",
        }
        if self.company_id.prepaid_countdown_journal_id:
            vals["journal_id"] = self.company_id.prepaid_countdown_journal_id.id
        return vals

    def _manage_prepaid_lines(self):
        self.ensure_one()
        prepaid_lines = self.invoice_line_ids.filtered(
            lambda line: line.product_id.prepaid_revenue_account_id
        )
        if not prepaid_lines:
            return self.browse(False)
        prepaid_move = self.prepaid_countdown_move_id
        if prepaid_move:
            if prepaid_move.state != "cancel":
                raise exceptions.ValidationError(
                    _("The linked prepaid entry should be canceled.")
                )
            prepaid_move.with_context(prepaid_reset=True).button_draft()
            prepaid_move.line_ids.unlink()
        else:
            vals = self._create_prepare_prepaid_move_vals()
            prepaid_move = self.create(vals)
            self.write({"prepaid_countdown_move_id": prepaid_move.id})
        line_vals_list = []
        account_amounts = defaultdict(float)
        for prepaid_line in prepaid_lines:
            #            line_vals = {
            #            "name": prepaid_line.name,
            #            "account_id": prepaid_line.account_id.id,
            #            "amount_currency": -prepaid_line.amount_currency,
            #            "move_id": prepaid_move.id,
            #            }
            #            line_vals = self.env["account.move.line"].play_onchanges(
            #                line_vals, ["account_id", "amount_currency"]
            #            )
            #            line_vals_list.append(line_vals)
            if (
                not prepaid_line.product_id.prepaid_revenue_account_id
                or not prepaid_line.product_id.property_account_income_id
            ):
                raise
            account_amounts[
                (
                    prepaid_line.product_id.prepaid_revenue_account_id,
                    prepaid_line.product_id.property_account_income_id,
                    prepaid_line.analytic_account_id,
                )
            ] += prepaid_line.amount_currency
        for (
            prepaid_revenue_accout,
            revenue_account,
            analytic_account,
        ), amount_curr in account_amounts.items():
            # prepaid line
            # Add AK contribution
            name = "prepaid transfer from invoice %s - %s" % (
                self.name,
                self.customer_id.name,
            )
            contribution = self.company_id.with_context(
                partner=analytic_account.partner_id
            )._get_commission_rate()
            amount = amount_curr / (1 - contribution)
            line_vals = {
                "name": name,
                "account_id": prepaid_revenue_accout.id,
                "amount_currency": amount,
                "move_id": prepaid_move.id,
                "partner_id": analytic_account.partner_id.id,
                "analytic_account_id": analytic_account.id,
            }
            line_vals = self.env["account.move.line"].play_onchanges(
                line_vals, ["account_id", "amount_currency"]
            )
            line_vals_list.append(line_vals)
            # revenu line
            line_vals = {
                "name": name,
                "account_id": revenue_account.id,
                "amount_currency": -amount,
                "move_id": prepaid_move.id,
                "analytic_account_id": analytic_account.id,
            }
            line_vals = self.env["account.move.line"].play_onchanges(
                line_vals, ["account_id", "amount_currency"]
            )
            line_vals_list.append(line_vals)
        prepaid_move.write({"line_ids": [(0, 0, vals) for vals in line_vals_list]})
        prepaid_move.action_post()
        return prepaid_move

    def _check_invoice_mode_validity(self):
        self.ensure_one()
        for line in self.invoice_line_ids:
            if (
                line.product_id.prepaid_revenue_account_id
                and not line.analytic_account_id
            ):
                raise exceptions.ValidationError(
                    _(
                        "Line %s is not valid, the analytic_account is mandatory."
                        % line.name
                    )
                )
        if self.is_supplier_prepaid and not all(
            [
                line.product_id.prepaid_revenue_account_id
                for line in self.invoice_line_ids
            ]
        ):
            raise exceptions.ValidationError(
                _(
                    "All invoice lines of a supplier invoice with prepaid product "
                    "should be consistent"
                )
            )

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        for move in self:
            move._check_invoice_mode_validity()
            if move.is_supplier_prepaid:
                move._manage_prepaid_lines()
                move.compute_enought_analytic_amount(partner_id=move.customer_id.id)
        return res

    def _check_reset_allowed(self):
        prepaid_move = self.filtered(lambda m: m.supplier_invoice_ids)
        if prepaid_move and not self.env.context.get("prepaid_reset"):
            raise exceptions.ValidationError(
                _(
                    "You can't reset a prepaid acconting entry as it is synchronized "
                    "automatically with its linked supplier invoice"
                )
            )

    def button_draft(self):
        self._check_reset_allowed()
        res = super().button_draft()
        if self.prepaid_countdown_move_id:
            self.prepaid_countdown_move_id.with_context(
                prepaid_reset=True
            ).button_cancel()
        return res

    def button_cancel(self):
        self._check_reset_allowed()
        res = super().button_cancel()
        if self.prepaid_countdown_move_id:
            self.prepaid_countdown_move_id.with_context(
                prepaid_reset=True
            ).button_cancel()
        return res

    # also called by cron
    @api.model
    def compute_enought_analytic_amount(self, partner_id=False):
        # it concerns only subcontractor partner
        domain = [
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
            ("is_supplier_prepaid", "=", True),
        ]
        if partner_id:
            domain.append(("customer_id", "=", partner_id))
        invoices_to_check = self.search(domain, order="invoice_date")
        # We only need invoices with analytic account and all lines should have
        # analytic accounts we should avoid invoices generated from subcontract work.
        available_analytic_amount = {}
        to_pay_invoices = self.env["account.move"]
        for invoice in invoices_to_check:
            to_pay = True
            prepaid_move = invoice.prepaid_countdown_move_id
            if not prepaid_move:
                continue
            for line in prepaid_move.line_ids:
                if (
                    not line.account_id.is_prepaid_account
                    or not line.analytic_account_id
                ):
                    continue
                account = line.analytic_account_id
                if account not in available_analytic_amount:
                    available_analytic_amount[account] = account.available_amount
                if abs(line.amount_currency) > available_analytic_amount[account]:
                    available_analytic_amount[account] = 0.0
                    to_pay = False
                    break
                else:
                    available_analytic_amount[account] -= abs(line.amount_currency)
            if to_pay:
                to_pay_invoices |= invoice
        to_pay_invoices.write({"enough_analytic_amount": True})
        (invoices_to_check - to_pay_invoices).write({"enough_analytic_amount": False})

    @api.depends(
        "enough_analytic_amount",
    )
    def _compute_to_pay(self):
        super()._compute_to_pay()
        for invoice in self:
            if invoice.enough_analytic_amount and invoice.payment_state not in (
                "reversed",
                "paid",
            ):
                invoice.to_pay = True
