# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import _, api, fields, models


class SubcontractorTimesheetInvoice(models.TransientModel):
    _name = "subcontractor.timesheet.invoice"

    partner_id = fields.Many2one("res.partner", readonly=True)
    create_invoice = fields.Boolean(
        help="Check this box if you do not want to use an existing invoice but create "
        "a new one instead."
    )
    invoice_id = fields.Many2one("account.invoice")
    error = fields.Text(readonly=True)

    def _get_partner_ids(self):
        partner_ids = []
        line_ids = self.env.context["active_ids"]
        datas = self.env["account.analytic.line"].read_group(
            [("id", "in", line_ids)], "partner_id", "partner_id"
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

    def _extract_timesheet(self):
        """Return a dict with
        { <task_id> :
            {<employee_id> : <timesheet_line_ids>}
        }
        """
        res = {}
        line_obj = self.env["account.analytic.line"]
        group_lines = line_obj.read_group(
            [("id", "in", self._context["active_ids"])],
            ["task_id", "user_id", "unit_amount"],
            ["task_id", "user_id"],
            lazy=False,
        )
        for group in group_lines:
            task_id = group["task_id"][0]
            user = self.env["res.users"].browse(group["user_id"][0])
            # TODO found a better solution then getting the first employee
            employee_id = user.employee_ids[0].id
            lines = line_obj.search(group["__domain"])
            if task_id not in res:
                res[task_id] = {employee_id: lines.ids}
            else:
                res[task_id][employee_id] = lines.ids
        return res

    def _prepare_subcontractor_work(self, inv_line_id, employee_id, line_ids):
        lines = self.env["account.analytic.line"].browse(line_ids)
        vals = {
            "employee_id": employee_id,
            "quantity": sum(
                [line._get_invoiceable_qty_with_project_unit() for line in lines]
            ),
            "invoice_line_id": inv_line_id,
            "timesheet_line_ids": [(6, 0, line_ids)],
        }
        record = self.env["subcontractor.work"].new(vals)
        record.employee_id_onchange()
        record._compute_price()
        vals.update(
            {
                "sale_price_unit": record.sale_price_unit,
                "cost_price_unit": record.cost_price_unit,
                "subcontractor_type": record.subcontractor_type,
            }
        )
        return vals

    def _prepare_invoice_line(self, task_id, data):
        line_obj = self.env["account.invoice.line"]
        task = self.env["project.task"].browse(task_id)
        product = task.project_id.product_id
        vals = {
            "task_id": task_id,
            "invoice_id": self.invoice_id.id,
            "product_id": product.id,
            "name": u"[{}] {}".format(task.id, task.name),
            "subcontracted": True,
            "uom_id": task.project_id.uom_id.id,
        }
        vals = line_obj.play_onchanges(vals, ["product_id"])
        return vals

    def _add_update_invoice_line(self, task_id, data):
        line_obj = self.env["account.invoice.line"]
        work_obj = self.env["subcontractor.work"]
        line = line_obj.search(
            [("invoice_id", "=", self.invoice_id.id), ("task_id", "=", task_id)]
        )
        if not line:
            line_vals = self._prepare_invoice_line(task_id, data)
            line = line_obj.create(line_vals)
        else:
            lines = line.subcontractor_work_ids.mapped("timesheet_line_ids")
            line.subcontractor_work_ids.unlink()
            active_ids = self.env.context["active_ids"] + lines.ids
            data = self.with_context(active_ids=active_ids)._extract_timesheet()[
                task_id
            ]
        # TODO FIX unit conversion
        qty_day = 0
        for employee_id, line_ids in data.items():
            val = self._prepare_subcontractor_work(line.id, employee_id, line_ids)
            qty_day += val["quantity"]
            work_obj.create(val)
        line.quantity = qty_day

    def _get_invoice_vals(self):
        self.ensure_one()
        # we do not manage case where partner_ids contain more than 1 element or False
        # inside, because in this case, the button is hidden and so this action should
        # not be done at all.
        partner_id = self._get_partner_ids()[0]
        vals = {"partner_id": partner_id, "type": "out_invoice"}
        vals = self.env["account.invoice"].play_onchanges(vals, ["partner_id"])
        return vals

    @api.multi
    def action_invoice(self):
        self.ensure_one()
        # TODO
        # récupérer des données structuré
        # {tak_id: ('employee_id', time, timesheet_ids)}
        res = self._extract_timesheet()
        if self.create_invoice:
            invoice_vals = self._get_invoice_vals()
            invoice = self.env["account.invoice"].create(invoice_vals)
            self.invoice_id = invoice.id
        # In case that you no account define on the product
        # Odoo will use default value from journal
        # we need to set this value to avoid empty account
        # on invoice line
        self = self.with_context(journal_id=self.invoice_id.journal_id.id)
        for task_id, data in res.items():
            self._add_update_invoice_line(task_id, data)
        self.invoice_id.compute_taxes()

        # return the invoice view
        action = self.env.ref("account.action_invoice_tree1").read()[0]
        action["views"] = [(self.env.ref("account.invoice_form").id, "form")]
        action["res_id"] = self.invoice_id.id
        return action
