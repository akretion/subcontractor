# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from collections import defaultdict

from odoo import _, api, exceptions, fields, models
from odoo.fields import first
from odoo.tools import float_compare


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
    subcontractor_state_message = fields.Text(
        compute="_compute_subcontractor_state", compute_sudo=True
    )
    subcontractor_state_color = fields.Char(
        compute="_compute_subcontractor_state", compute_sudo=True
    )
    invoicing_mode = fields.Char(compute="_compute_invoicing_mode", store=True)

    @api.depends("invoice_line_ids.analytic_account_id")
    def _compute_invoicing_mode(self):
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            modes = move.invoice_line_ids.analytic_account_id.project_ids.mapped(
                "invoicing_mode"
            )
            move.invoicing_mode = (
                modes and all(x == modes[0] for x in modes) and modes[0] or False
            )

    def _prepaid_account_amounts(self):
        self.ensure_one()
        prepaid_lines = self.invoice_line_ids.filtered(
            lambda line: line.product_id.prepaid_revenue_account_id
        )
        account_amounts = defaultdict(float)
        fpos = self.customer_id.property_account_position_id

        for prepaid_line in prepaid_lines:
            accounts = prepaid_line.product_id.product_tmpl_id.get_product_accounts(
                fiscal_pos=fpos
            )
            prepaid_account = accounts.get("prepaid")
            revenue_account = accounts.get("income")
            account_amounts[
                (
                    prepaid_account,
                    revenue_account,
                    prepaid_line.analytic_account_id,
                )
            ] += prepaid_line.contribution_price_subtotal
        return account_amounts

    @api.depends("invoice_line_ids.analytic_account_id")
    def _compute_customer_id(self):
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            partner = first(
                move.invoice_line_ids.analytic_account_id.project_ids
            ).partner_id
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

    def _compute_subcontractor_state(self):  # noqa: C901
        precision = self.env["decimal.precision"].precision_get("Account")
        for inv in self:
            reason = ""
            color = ""
            if (
                inv.move_type != "in_invoice"
                or inv.payment_state == "paid"
                or inv.state == "cancel"
            ):
                inv.subcontractor_state_message = reason
                inv.subcontractor_state_color = color
                continue
            if inv.to_pay:
                if inv.line_ids.payment_line_ids:
                    reason = (
                        "La facture a été ajoutée au prochain ordre de paiement qui "
                        "est à l'état '%s'.\nElle devrait être payée dans les prochains"
                        " jours"
                        "" % inv.line_ids.payment_line_ids.mapped("state")[0]
                    )
                    color = "success"
                else:
                    reason = (
                        "La facture est à payer, elle sera incluse dans le prochain "
                        "ordre de paiement."
                    )
                    color = "success"
            elif inv.customer_invoice_ids:
                if (
                    inv.state == "draft"
                    and inv.auto_invoice_id
                    and float_compare(
                        inv.amount_total,
                        inv.auto_invoice_id.amount_total,
                        precision_digits=precision,
                    )
                ):
                    reason = (
                        "La facture est en brouillon car le montant de la facture ne "
                        "correspond pas à celui de la facture inter société."
                    )
                    color = "danger"
                if inv.invalid_work_amount:
                    reason = (
                        "Le montant des lignes de factures n'est pas cohérent avec le "
                        "montant des lignes de sous-traitance."
                    )
                    color = "danger"
                if any([x.payment_state != "paid" for x in inv.customer_invoice_ids]):
                    reason = (
                        "Les factures clients Akretion %s ne sont pas encore payées ou"
                        " leur paiement n'a pas encore été importé dans l'erp."
                        % ", ".join(inv.customer_invoice_ids.mapped("name"))
                    )
                    color = "info"
            elif inv.is_supplier_prepaid:
                account_amounts = inv._prepaid_account_amounts()
                account_reasons = []
                other_draft_invoices = self.env["account.move"]
                for (
                    _prepaid_revenue_account,
                    _revenue_account,
                    analytic_account,
                ), amount in account_amounts.items():
                    # read on project not very intuitive to discuss
                    if not analytic_account:
                        reason = (
                            "Le compte analytique est obligatoire sur les lignes de "
                            "cette facture."
                        )
                        break
                    total_amount = analytic_account.prepaid_total_amount
                    available_amount = analytic_account.prepaid_available_amount
                    if inv.state == "draft":
                        other_draft_invoices = self.env["account.move.line"].search(
                            [
                                ("parent_state", "=", "draft"),
                                (
                                    "analytic_account_id",
                                    "=",
                                    analytic_account.id,
                                ),
                                ("move_id", "!=", inv.id),
                                ("move_id.move_type", "=", ["in_invoice", "in_refund"]),
                            ]
                        )
                    if (
                        inv.state == "draft"
                        and float_compare(
                            total_amount, amount, precision_digits=precision
                        )
                        == -1
                    ):
                        account_reasons.append(
                            f"Le solde du compte analytique {analytic_account.name} "
                            f"n'est pas suffisant : {total_amount}. "
                            f"Il est necessaire de facturer le client."
                        )
                        color = "danger"
                    elif inv.state == "draft" and (
                        float_compare(
                            available_amount, amount, precision_digits=precision
                        )
                        == -1
                    ):
                        account_reasons.append(
                            f"Le solde payé du compte analytique "
                            f"{analytic_account.name}"
                            f" est insuffisant {available_amount}. "
                            f"La facture sera payable une fois que le client aura reglé"
                            f"ses factures."
                        )
                        if color != "red":
                            color = "info"
                    elif (
                        inv.state != "draft"
                        and float_compare(total_amount, 0, precision_digits=precision)
                        == -1
                    ):
                        account_reasons.append(
                            f"Le solde du compte analytique {analytic_account.name} "
                            f"est négatif {total_amount}. "
                            f"Il est necessaire de facturer le client."
                        )
                        color = "danger"
                    elif inv.state != "draft" and (
                        float_compare(available_amount, 0, precision_digits=precision)
                        == -1
                    ):
                        account_reasons.append(
                            f"Le solde payé du compte analytique "
                            f"{analytic_account.name} est insuffisant "
                            f"{available_amount}. "
                            f"La facture sera payable une fois que le client aura reglé"
                            f" ses factures."
                        )
                        if color != "red":
                            color = "info"
                    else:
                        account_reasons.append(
                            f"Le solde payé du compte analytique "
                            f"{analytic_account.name} est suffisant. "
                            f"La facture sera payable une fois qu'elle sera validée et "
                            f"que la tâche planifiée aura tourné."
                        )
                        if not color:
                            color = "success"
                if other_draft_invoices:
                    account_reasons.append(
                        "Attention, il existe des factures à l'état 'brouillon' pour "
                        "ce/ces comptes analytiques, si elles sont validées, elles "
                        "peuvent influer les montants disponibles."
                    )
                reason = "\n".join(account_reasons)
            elif inv.invoicing_mode == "supplier":
                reason = (
                    "La validation et le paiement de cette facture se font manuellement"
                    " selon la gestion des budgets."
                )
            inv.subcontractor_state_message = reason
            inv.subcontractor_state_color = color

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
            if self.is_supplier_prepaid:
                lines = self.invoice_line_ids.timesheet_line_ids
            else:
                works = self.invoice_line_ids.subcontractor_work_invoiced_id
                lines = works.timesheet_line_ids
            action["domain"] = [("id", "=", lines.ids)]
        return action

    def _create_prepare_prepaid_move_vals(self):
        self.ensure_one()
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
        if not self.is_supplier_prepaid:
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
        account_amounts = self._prepaid_account_amounts()
        for (
            prepaid_revenue_account,
            revenue_account,
            analytic_account,
        ), amount in account_amounts.items():
            customer_name = self.customer_id.name
            # prepaid line
            name = f"prepaid transfer from invoice {self.name} - {customer_name}"
            line_vals = {
                "name": name,
                "account_id": prepaid_revenue_account.id,
                "amount_currency": amount,
                "move_id": prepaid_move.id,
                "partner_id": self.customer_id.id,
                "analytic_account_id": analytic_account.id,
            }
            line_vals_list.append(line_vals)
            # revenue line
            line_vals = {
                "name": name,
                "account_id": revenue_account.id,
                "amount_currency": -amount,
                "move_id": prepaid_move.id,
                "analytic_account_id": analytic_account.id,
            }
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
            if (
                line.product_id.prepaid_revenue_account_id
                and line.move_id.move_type in ("out_invoice", "out_refund")
            ):
                project_typology = first(
                    line.analytic_account_id.project_ids
                ).invoicing_typology_id
                if project_typology.product_id != line.product_id:
                    raise exceptions.ValidationError(
                        _(
                            "Line %s is not valid, the analytic_account is not "
                            "consistent with the chosen product" % line.name
                        )
                    )
                project_partner = first(line.analytic_account_id.project_ids).partner_id
                if project_partner != line.move_id.partner_id.commercial_partner_id:
                    raise exceptions.ValidationError(
                        _(
                            "Line %s is not valid, the analytic_account is not "
                            "consistent with the chosen customer" % line.name
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
                    "should be consistent."
                )
            )
        if self.is_supplier_prepaid and not self.customer_id:
            raise exceptions.ValidationError(
                _(
                    "You can't have a supplier invoice related to multiple end-customer"
                    "Check that all the analytic accounts of the line belong to the "
                    "same partner"
                )
            )
        modes = self.invoice_line_ids.analytic_account_id.project_ids.mapped(
            "invoicing_mode"
        )
        if modes and not all(x == modes[0] for x in modes):
            raise exceptions.ValidationError(
                _("All invoice lines should have the same invoicing mode.")
            )

    def _post(self, soft=True):
        for move in self:
            if move.subcontractor_state_color == "danger":
                raise exceptions.UserError(move.subcontractor_state_message)
            move._check_invoice_mode_validity()
        res = super()._post(soft=soft)
        for move in self:
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
        res = super()._compute_to_pay()
        for invoice in self:
            if invoice.enough_analytic_amount and invoice.payment_state not in (
                "reversed",
                "paid",
            ):
                invoice.to_pay = True
        return res

    def _is_invoiced_with_parent_task_option(self):
        """
        Res is True if invoice has been invoiced with parent task option
               False if invoice has been invoiced without parent task option
               None if it was not applicable. (no child task in the invoice)
        """
        self.ensure_one()
        res = None
        # check if invoice parent task was used during invoicing
        has_child_task = False
        for inv_line in self.invoice_line_ids:
            timesheet_tasks = inv_line.subcontractor_work_ids.timesheet_line_ids.task_id
            if not timesheet_tasks:
                continue
            if not has_child_task and inv_line.task_id.parent_id:
                has_child_task = True
            if len(timesheet_tasks) > 1 or (
                len(timesheet_tasks) == 1 and timesheet_tasks.id != inv_line.task_id
            ):
                res = True
                break
        if not res and has_child_task:
            res = False
        return res
