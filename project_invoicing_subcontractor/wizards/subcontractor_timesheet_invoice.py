# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import first


class SubcontractorTimesheetInvoice(models.TransientModel):
    _name = "subcontractor.timesheet.invoice"
    _description = "Wizard to invoice timesheet with subcontractor"

    @api.depends("timesheet_line_ids")
    def _compute_partner_id(self):
        timesheet_lines = self.timesheet_line_ids
        partners = timesheet_lines.partner_id
        for wizard in self:
            wizard.partner_id = len(partners) == 1 and partners.id or False

    @api.depends("partner_id", "force_project_id", "invoicing_mode")
    def _compute_to_invoice_partner_id(self):
        for wizard in self:
            if wizard.invoicing_mode == "customer_postpaid":
                if wizard.force_project_id:
                    wizard.to_invoice_partner_id = wizard.force_project_id.partner_id.id
                else:
                    wizard.to_invoice_partner_id = wizard.partner_id
            else:
                partners = self.env["res.partner"]
                for user in wizard.timesheet_line_ids.user_id:
                    employee = first(user.employee_ids)
                    partners |= employee._get_employee_invoice_partner()
                wizard.to_invoice_partner_id = (
                    len(partners) == 1 and partners.id or False
                )

    partner_id = fields.Many2one(
        "res.partner", compute="_compute_partner_id", store=True
    )
    to_invoice_partner_id = fields.Many2one(
        "res.partner", compute="_compute_to_invoice_partner_id", store=True
    )
    create_invoice = fields.Boolean(
        default=True,
        compute="_compute_create_invoice",
        store=True,
        readonly=False,
        help="Check this box if you do not want to use an existing invoice but create "
        "a new one instead.",
    )
    invoice_id = fields.Many2one(
        "account.move", compute="_compute_invoice", readonly=False, store=True
    )
    invoice_parent_task = fields.Boolean(
        compute="_compute_invoice_parent_task", store=True, readonly=False
    )
    has_parent_task = fields.Boolean(compute="_compute_has_parent_task")

    invoicing_typology_id = fields.Many2one(
        "project.invoice.typology", compute="_compute_invoicing_typology_id"
    )
    move_type = fields.Selection(
        [("out_invoice", "Customer Invoice"), ("in_invoice", "Supplier Invoice")],
        compute="_compute_move_type",
    )
    invoicing_mode = fields.Selection(related="invoicing_typology_id.invoicing_mode")
    error = fields.Text(compute="_compute_error", store=True)
    explanation = fields.Text(compute="_compute_explanation", store=True)
    force_project_id = fields.Many2one("project.project")
    timesheet_line_ids = fields.Many2many(
        "account.analytic.line",
        default=lambda self: self._get_default_timesheet_lines(),
    )

    @api.depends("invoice_id", "create_invoice")
    def _compute_invoice_parent_task(self):
        for rec in self:
            # In case an invoice is beeing modified, if invoice_parent_task option
            # was used when it was first created, it has to be used also during
            # modification. For consistency, of course, but also because the method
            # we use to update an invoice is to delete an invoice line and re-create
            # it. If we are not in the same mode, we may delete an invoice line
            # linked to multiple task and try to recreate multiple lines...It is
            # not what we want, and it is not implemented either, so it fails.
            if rec.invoice_id and not rec.create_invoice:
                is_invoiced_with_parent_task = (
                    rec.invoice_id._is_invoiced_with_parent_task_option()
                )
                # if result is None, there were no child task timesheet on the invoice
                # in that case, do not change the option choosen by user.
                if is_invoiced_with_parent_task is True:
                    rec.invoice_parent_task = True
                elif is_invoiced_with_parent_task is False:
                    rec.invoice_parent_task = False

    @api.depends("timesheet_line_ids")
    def _compute_has_parent_task(self):
        for record in self:
            timesheet_lines = self.timesheet_line_ids
            record.has_parent_task = bool(timesheet_lines.parent_task_id)

    @api.depends("invoicing_mode")
    def _compute_move_type(self):
        for rec in self:
            if rec.invoicing_mode == "customer_postpaid":
                rec.move_type = "out_invoice"
            else:
                rec.move_type = "in_invoice"

    @api.depends("to_invoice_partner_id")
    def _compute_create_invoice(self):
        for rec in self:
            if not rec.to_invoice_partner_id:
                rec.create_invoice = True

    @api.depends("to_invoice_partner_id")
    def _compute_invoice(self):
        for rec in self:
            if rec.invoice_id and (
                (
                    rec.to_invoice_partner_id
                    and rec.invoice_id.partner_id != rec.to_invoice_partner_id
                )
                or not rec.to_invoice_partner_id
            ):
                rec.invoice_id = False

    @api.depends(
        "to_invoice_partner_id", "invoicing_mode", "create_invoice", "force_project_id"
    )
    def _compute_explanation(self):
        for rec in self:
            explanation = ""
            if rec.invoicing_mode == "customer_postpaid" and rec.create_invoice:
                cus_name = rec.partner_id.name
                explanation = f"Une facture client va être créée pour {cus_name}"
            elif rec.invoicing_mode == "customer_postpaid" and rec.invoice_id:
                explanation = (
                    f"Les temps vont être facturés dans la facture client existante "
                    f"{rec.invoice_id.display_name} pour {rec.partner_id.name}"
                )
            elif rec.invoicing_mode == "customer_prepaid" and rec.create_invoice:
                explanation = (
                    f"Des factures fournisseurs vont être créées pour les sous "
                    f"traitants et décomptées des budget du client "
                    f"{rec.partner_id.name}"
                )
            elif rec.invoicing_mode == "customer_prepaid" and rec.invoice_id:
                explanation = (
                    f"Les temps vont être facturée dans la facture fournisseur "
                    f"existante {rec.invoice_id.display_name} et décomptés des budgets "
                    f"du client {rec.partner_id.name}"
                )
            rec.explanation = explanation

    def _get_default_timesheet_lines(self):
        ids = self.env.context.get("active_ids", False)
        return self.env["account.analytic.line"].browse(ids)

    @api.depends("timesheet_line_ids", "force_project_id")
    def _compute_invoicing_typology_id(self):
        timesheet_lines = self.timesheet_line_ids
        for rec in self:
            if rec.force_project_id:
                rec.invoicing_typology_id = (
                    rec.force_project_id.invoicing_typology_id.id
                )
            else:
                rec.invoicing_typology_id = (
                    len(timesheet_lines.project_id.invoicing_typology_id) == 1
                    and timesheet_lines.project_id.invoicing_typology_id.id
                    or False
                )

    def _get_partner_ids(self):
        partner_ids = []
        line_ids = self.timesheet_line_ids.ids
        datas = self.env["account.analytic.line"].read_group(
            [("id", "in", line_ids)], ["partner_id"], ["partner_id"]
        )
        partner_ids = [x["partner_id"] and x["partner_id"][0] or False for x in datas]
        return partner_ids

    def _get_partner_error(self):
        error = False
        partner_ids = self._get_partner_ids()
        if False in partner_ids:
            error = _(
                "One or more line is not linked to any partner. Fix this to be able to "
                "invoice it."
            )
        #        elif not self.force_project_id and len(partner_ids) != 1:
        elif len(partner_ids) != 1:
            partners = self.env["res.partner"].browse(partner_ids)
            error = _(
                "You can only invoice timesheet with the same partner. "
                "Partner found %s"
            ) % [x.name for x in partners]
        return error

    def _get_invoicing_typology_error(self, timesheet_lines):
        projects = timesheet_lines.project_id
        error = False
        if any([not proj.invoicing_typology_id for proj in projects]):
            error = _(
                "At least one of the chosen project is not  configured to be invoiced."
            )
        invoicing_typology = projects.invoicing_typology_id
        if (
            not self.force_project_id
            and len(list(set(invoicing_typology.mapped("invoicing_mode")))) > 1
        ):
            error = _(
                "You try to invoice timesheet from multiple projects that are not "
                "configured to be invoiced in the same way."
            )
        return error

    @api.depends("force_project_id", "timesheet_line_ids")
    def _compute_error(self):
        timesheet_lines = self.timesheet_line_ids
        error = self._get_partner_error()
        if not error and timesheet_lines.invoice_line_id:
            error = _("Some selected timesheet lines have already been invoiced")

        if not error:
            error = self._get_invoicing_typology_error(timesheet_lines)
        for wizard in self:
            wizard.error = error

    def _extract_timesheet(self, timesheet_lines, result=None):
        """Return a dict with
        { <task_id> :
            {<employee_id> : <timesheet_line_ids>}
        }
        if a result is passed, then it will complete this result
        """
        if result is None:
            result = {}
        for timesheet_line in timesheet_lines:
            task = timesheet_line.task_id
            if task.parent_id and self.invoice_parent_task:
                if task.project_id != task.parent_id.project_id:
                    raise UserError(
                        _(
                            "Task '%(task_name)s' do not belong to the same "
                            "project of the parent task '%(parent_task_name)s'"
                        )
                        % dict(
                            task_name=task.name,
                            parent_task_name=task.parent_id.name,
                        )
                    )
                task = task.parent_id
            task_id = task.id
            if task_id not in result:
                result[task_id] = {}
            employee_id = timesheet_line.employee_id.id
            if employee_id not in result[task_id]:
                result[task_id][employee_id] = []
            if timesheet_line.id not in result[task_id][employee_id]:
                result[task_id][employee_id].append(timesheet_line.id)
        return result

    def _prepare_subcontractor_work(self, employee_id, line_ids):
        lines = self.env["account.analytic.line"].browse(line_ids)
        vals = {
            "employee_id": employee_id,
            "quantity": lines._get_invoiceable_qty_with_project_unit(),
            "timesheet_line_ids": [(6, 0, line_ids)],
        }
        vals = self.env["subcontractor.work"].play_onchanges(vals, ["employee_id"])
        return vals

    def _prepare_invoice_line(self, invoice, task, timesheet_lines):
        line_obj = self.env["account.move.line"]
        project = self.force_project_id or task.project_id
        product = project.invoicing_typology_id.product_id

        # The total qty is not the sum of all subcontractor work to avoid
        # rounding issue for the customer, we will rounding difference
        # between akretion and members but it's not an issue
        quantity = timesheet_lines._get_invoiceable_qty_with_project_unit()
        vals = {
            "task_id": task.id,
            "move_id": invoice.id,
            "product_id": product.id,
            "name": f"[{task.id}] {task.name}",
            "product_uom_id": task.project_id.uom_id.id,
            "quantity": quantity,
        }
        if hasattr(self.env["account.move.line"], "start_date") and hasattr(
            self.env["account.move.line"], "end_date"
        ):
            start_date = min(timesheet_lines.mapped("date"))
            end_date = max(timesheet_lines.mapped("date"))
            vals.update(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
        if project.invoicing_typology_id.invoicing_mode != "customer_postpaid":
            vals["analytic_account_id"] = project.analytic_account_id.id
            vals["price_unit"] = project.price_unit
            if project.invoicing_typology_id.invoicing_mode == "customer_prepaid":
                contribution = invoice.company_id._get_commission_rate()
                vals["price_unit"] = (1 - contribution) * vals["price_unit"]
        # TODO test price unit for prepaid, postpaid et supplier avec le force

        # onchange_product_id call the product_uom_id on change but with default
        # product_uom (like in UI) So, the uom we give is erased and the price unit
        # is wrong. But AFAIK playonchanges does not erase a given value on original
        # dict. So the call to product_uom_id on change will keep the uom we gave
        # but we need to play both onchanges...

        # it is important to play the onchanges here because of a (very) obscure bug.
        # if we do not play onchange, when we write the invoice_line_ids on the invoice
        # odoo will unlink all existing lines and create new one, so we loose the link
        # between the timesheet lines and the invoice line.
        # when we play the onchange, I don't know why but odoo's behavior is different
        # it will keep the existing invoice lines and so keep the link.
        # As far as I saw, during the write of invoice_line_ids, odoo goes there :
        # _move_autocomplete_invoice_lines_write and invoice_new.line_ids are
        # NewId without origin if we did not play the onchange and with origin if
        # onchange helper was used.
        # Then when it goes in _move_autocomplete_invoice_lines_values and if
        # convert the record to write, if the NewId invoice lines have no origin
        # Odoo will unlink old lines and create new one. If NewId origin is set
        # it will keep the old lines.
        # the test catch the bug anyway...

        # I keep the above comment until v16 but we actually really need the onchange
        # anyway now, to get the right account and price.
        vals = line_obj.play_onchanges(vals, ["product_id", "product_uom_id"])

        return vals

    def _get_invoice_line_vals_list(self, invoice, task_id, all_data):
        """
        return list of vals to be written on account.move.invoice_line_ids
        [(x, y, z)] ...
        """
        inv_line_obj = self.env["account.move.line"]
        inv_line = inv_line_obj.search(
            [("move_id", "=", invoice.id), ("task_id", "=", task_id)]
        )
        # if invoice line exists already we need to consider current timesheet lines
        # (in all data) + the already invoiced timesheet so we add the already invoiced
        # timesheet lines in all_data dict
        if inv_line:
            all_data = self._extract_timesheet(
                inv_line.subcontractor_work_ids.timesheet_line_ids, result=all_data
            )

        all_task_timesheet_line_ids = []
        task_data = all_data[task_id]
        for _employee_id, timesheet_line_ids in task_data.items():
            all_task_timesheet_line_ids += timesheet_line_ids

        timesheet_lines = self.env["account.analytic.line"].browse(
            all_task_timesheet_line_ids
        )

        task = self.env["project.task"].browse(task_id)
        line_vals = self._prepare_invoice_line(invoice, task, timesheet_lines)
        # add subcontractors vals
        subcontractor_vals = []
        for employee_id, line_ids in task_data.items():
            val = self._prepare_subcontractor_work(employee_id, line_ids)
            subcontractor_vals.append((0, 0, val))
        if subcontractor_vals:
            line_vals["subcontractor_work_ids"] = subcontractor_vals
            line_vals["subcontracted"] = True

        if not inv_line:
            invoice_line_vals_list = [(0, 0, line_vals)]
        else:
            inv_line.subcontractor_work_ids.unlink()
            # we can't just do a [(1, id, vals)] here because the invoicing
            # creation/update outside the UI is totally fucked up...
            # so the workaround is to create a new one and delete the old one in the
            # same write. I guess it is acceptable here to delete and create the new
            # one, we should not loose anything.
            # Maybe we should stop allowing the update on lines, the user could just
            # delete the invoice lines himself and then create a new one...
            # or spend more time to find a cleaner way.
            invoice_line_vals_list = [(0, 0, line_vals), (2, inv_line.id, 0)]
        return invoice_line_vals_list

    def _get_invoice_vals(self, partner):
        self.ensure_one()
        invoicing_mode = self.invoicing_typology_id.invoicing_mode
        move_type = (
            invoicing_mode == "customer_postpaid" and "out_invoice" or "in_invoice"
        )
        vals = {"partner_id": partner.id, "move_type": move_type}
        if move_type == "in_invoice":
            vals["invoice_date"] = fields.Date.today()
        vals = self.env["account.move"].play_onchanges(vals, ["partner_id"])
        return vals

    def action_customer_invoice(self):
        # TODO
        # récupérer des données structuré
        # {tak_id: ('employee_id', time, timesheet_ids)}
        timesheet_lines = self.timesheet_line_ids
        res = self._extract_timesheet(timesheet_lines)
        if self.create_invoice:
            invoice_vals = self._get_invoice_vals(self.to_invoice_partner_id)
            invoice = self.env["account.move"].create(invoice_vals)
        else:
            invoice = self.invoice_id
            # self.invoice_id = invoice.id
        # In case that you no account define on the product
        # Odoo will use default value from journal
        # we need to set this value to avoid empty account
        # on invoice line
        # TODO check if still usefull
        #        self = self.with_context(journal_id=self.invoice_id.journal_id.id)
        invoice_line_vals_list = []
        for task_id, _data in res.items():
            invoice_line_vals_list += self._get_invoice_line_vals_list(
                invoice, task_id, res
            )
        # we do only one write as odoo recompute all amls for each write which is
        # not efficient
        invoice.write({"invoice_line_ids": invoice_line_vals_list})

        # return the invoice view
        action = self.env.ref("account.action_move_out_invoice_type").sudo().read()[0]
        action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
        action["res_id"] = invoice.id
        return action

    def _get_timesheet_by_task_by_employee(self):
        res = defaultdict(
            lambda: defaultdict(lambda: self.env["account.analytic.line"])
        )
        for line in self.timesheet_line_ids:
            employee = first(line.user_id.employee_ids)
            partner = employee._get_employee_invoice_partner()
            res[partner][line.task_id] |= line
        return res

    def _add_update_invoice_line(self, invoice, task, tlines):
        inv_line = task.invoice_line_ids.filtered(lambda s: s.move_id == invoice)
        if inv_line:
            tlines |= inv_line.timesheet_line_ids
        vals = self._prepare_invoice_line(invoice, task, tlines)
        if not inv_line:
            invoice.write({"invoice_line_ids": [(0, 0, vals)]})
            inv_line = task.invoice_line_ids.filtered(lambda s: s.move_id == invoice)
        else:
            invoice.write({"invoice_line_ids": [(0, 0, vals), (2, inv_line.id, 0)]})
            inv_line = invoice.invoice_line_ids.filtered(
                lambda line: line.task_id == task
            )
        tlines.write({"supplier_invoice_line_id": inv_line.id})

    def action_supplier_invoice(self):
        self.ensure_one()
        data = self._get_timesheet_by_task_by_employee()
        # should not happens since it should not be possible from the UI but we never
        # know...
        if len(data) > 1 and not self.create_invoice:
            raise UserError(
                _(
                    "Multiple subcontractor are selected, you can't choose an existing"
                    " invoice to invoice the timesheet lines"
                )
            )
        invoices = self.env["account.move"]
        for partner, task2tlines in data.items():
            if self.create_invoice:
                invoice_vals = self._get_invoice_vals(partner)
                invoice = self.env["account.move"].create(invoice_vals)
            else:
                invoice = self.invoice_id
            # self = self.with_context(journal_id=self.invoice_id.journal_id.id)
            for task, tlines in task2tlines.items():
                self._add_update_invoice_line(invoice, task, tlines)
            invoices |= invoice

        # return the invoice view
        action = self.env.ref("account.action_move_in_invoice_type").sudo().read()[0]
        if len(invoices) == 1:
            action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
            action["res_id"] = invoices.id
        else:
            action["domain"] = [("id", "in", invoices.ids)]
        return action
