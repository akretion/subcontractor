# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import _, api, fields, models


class SubcontractorTimesheetInvoice(models.TransientModel):
    _name = "subcontractor.timesheet.invoice"
    _description = "Wizard to invoice timesheet with subcontractor"

    partner_id = fields.Many2one("res.partner", readonly=True)
    create_invoice = fields.Boolean(
        help="Check this box if you do not want to use an existing invoice but create "
        "a new one instead."
    )
    invoice_id = fields.Many2one("account.move")
    error = fields.Text(readonly=True)
    invoice_parent_task = fields.Boolean()
    has_parent_task = fields.Boolean(compute="_compute_has_parent_task")

    @api.depends_context("active_ids")
    @api.depends("partner_id")
    def _compute_has_parent_task(self):
        for record in self:
            timesheet_lines = self.env["account.analytic.line"].browse(
                self.env.context.get("active_ids", [])
            )
            record.has_parent_task = bool(timesheet_lines.parent_task_id)

    def _get_partner_ids(self):
        partner_ids = []
        line_ids = self.env.context["active_ids"]
        datas = self.env["account.analytic.line"].read_group(
            [("id", "in", line_ids)], ["partner_id"], ["partner_id"]
        )
        partner_ids = [x["partner_id"] and x["partner_id"][0] or False for x in datas]
        return partner_ids

    @api.onchange("error")
    def onchange_error(self):
        partner_ids = self._get_partner_ids()
        if False in partner_ids:
            self.error = _(
                "One or more line is not linked to any partner. Fix this to be able to "
                "invoice it."
            )
        elif len(partner_ids) == 1:
            self.partner_id = partner_ids[0]
        else:
            partners = self.env["res.partner"].browse(partner_ids)
            self.error = _(
                "You can only invoice timesheet with the same partner."
                "Partner found %s"
            ) % [x.name for x in partners]
        timesheet_lines = self.env["account.analytic.line"].browse(
            self.env.context["active_ids"]
        )
        if timesheet_lines.invoice_line_id:
            self.error = _("Some selected timesheet lines have already been invoiced")

    #    def _extract_timesheet(self, timesheet_lines):
    #        """Return a dict with
    #        { <task_id> :
    #            {<employee_id> : <timesheet_line_ids>}
    #        }
    #        """
    #        res = {}
    #        line_obj = self.env["account.analytic.line"]
    #        group_lines = line_obj.read_group(
    #            [("id", "in", timesheet_lines.ids)],
    #            ["task_id", "user_id", "unit_amount"],
    #            ["task_id", "user_id"],
    #            lazy=False,
    #        )
    #        for group in group_lines:
    #            task_id = group["task_id"][0]
    #            user = self.env["res.users"].browse(group["user_id"][0])
    #            # TODO found a better solution then getting the first employee
    #            employee_id = user.employee_ids[0].id
    #            lines = line_obj.search(group["__domain"])
    #            if task_id not in res:
    #                res[task_id] = {employee_id: lines.ids}
    #            else:
    #                res[task_id][employee_id] = lines.ids
    #        return res

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

    def _prepare_invoice_line(self, task, timesheet_lines, data):
        line_obj = self.env["account.move.line"]
        product = task.project_id.product_id
        # The total qty is not the sum of all subcontractor work to avoid
        # rounding issue for the customer, we will rounding difference
        # between akretion and members but it's not an issue
        quantity = timesheet_lines._get_invoiceable_qty_with_project_unit()
        vals = {
            "task_id": task.id,
            "move_id": self.invoice_id.id,
            "product_id": product.id,
            "name": "[{}] {}".format(task.id, task.name),
            "subcontracted": True,
            "product_uom_id": task.project_id.uom_id.id,
            "quantity": quantity,
        }
        # onchange_product_id call the product_uom_id on change but with default
        # product_uom (like in UI) So, the uom we give is erased and the price unit
        # is wrong. But AFAIK playonchanges does not erase a given value on original
        # dict. So the call to product_uom_id on change will keep the uom we gave
        # but we need to play both onchanges...
        vals = line_obj.play_onchanges(vals, ["product_id", "product_uom_id"])

        subcontractor_vals = []
        for employee_id, line_ids in data.items():
            val = self._prepare_subcontractor_work(employee_id, line_ids)
            subcontractor_vals.append((0, 0, val))
        if subcontractor_vals:
            vals["subcontractor_work_ids"] = subcontractor_vals
        return vals

    def _get_invoice_line_vals_list(self, task_id, all_data):
        """
        return list of vals to be written on account.move.invoice_line_ids
        [(x, y, z)] ...
        """
        inv_line_obj = self.env["account.move.line"]
        inv_line = inv_line_obj.search(
            [("move_id", "=", self.invoice_id.id), ("task_id", "=", task_id)]
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
        line_vals = self._prepare_invoice_line(task, timesheet_lines, task_data)
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

    def _get_invoice_vals(self):
        self.ensure_one()
        # we do not manage case where partner_ids contain more than 1 element or False
        # inside, because in this case, the button is hidden and so this action should
        # not be done at all.
        partner_id = self._get_partner_ids()[0]
        vals = {"partner_id": partner_id, "move_type": "out_invoice"}
        vals = self.env["account.move"].play_onchanges(vals, ["partner_id"])
        return vals

    def action_invoice(self):
        self.ensure_one()
        # TODO
        # récupérer des données structuré
        # {tak_id: ('employee_id', time, timesheet_ids)}
        timesheet_lines = self.env["account.analytic.line"].browse(
            self.env.context.get("active_ids", [])
        )
        res = self._extract_timesheet(timesheet_lines)
        if self.create_invoice:
            invoice_vals = self._get_invoice_vals()
            invoice = self.env["account.move"].create(invoice_vals)
            self.invoice_id = invoice.id
        # In case that you no account define on the product
        # Odoo will use default value from journal
        # we need to set this value to avoid empty account
        # on invoice line
        # TODO check if still usefull
        self = self.with_context(journal_id=self.invoice_id.journal_id.id)
        invoice_line_vals_list = []
        for task_id, _data in res.items():
            invoice_line_vals_list += self._get_invoice_line_vals_list(task_id, res)
        # we do only one write as odoo recompute all amls for each write which is
        # not efficient
        self.invoice_id.write({"invoice_line_ids": invoice_line_vals_list})

        # return the invoice view
        action = self.env.ref("account.action_move_out_invoice_type").sudo().read()[0]
        action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
        action["res_id"] = self.invoice_id.id
        return action
