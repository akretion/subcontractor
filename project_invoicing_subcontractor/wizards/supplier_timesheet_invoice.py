# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SupplierTimesheetInvoice(models.TransientModel):
    _name = "supplier.timesheet.invoice"
    _description = "Wizard to invoice supplier timesheet"

    employee_id = fields.Many2one(
        "hr.employee", string="Subcontractor", compute="_compute_employee"
    )
    partner_id = fields.Many2one("res.partner", compute="_compute_employee")
    create_invoice = fields.Boolean(
        help="Check this box if you do not want to use an existing invoice but create "
        "a new one instead.",
        default=True,
    )
    invoice_id = fields.Many2one("account.move")
    error = fields.Text(compute="_compute_employee")
    force_project_id = fields.Many2one(
        "project.project", domain=[("invoicing_mode", "=", "supplier")]
    )

    def _get_tlines(self):
        return self.env["account.analytic.line"].browse(self._context.get("active_ids"))

    def _get_task2tlines(self):
        res = defaultdict(lambda: self.env["account.analytic.line"])
        for line in self._get_tlines():
            res[line.task_id] |= line
        return res

    @api.depends("create_invoice")
    def _compute_employee(self):
        for record in self:
            tlines = self._get_tlines()
            if len(tlines.mapped("user_id")) > 1:
                record.error = "You should invoice only one subcontractor"
                record.employee_id = False
                record.partner = False
            else:
                record.error = False
                record.employee_id = tlines.mapped("user_id.employee_ids")[0]
                record.partner_id = (
                    record.employee_id.subcontractor_company_id.partner_id
                )

    def _prepare_invoice_line(self, task, tlines):
        line_obj = self.env["account.move.line"]
        project = self.force_project_id or task.project_id
        if project.invoicing_mode != "supplier":
            raise UserError(
                _("You can not generate supplier timesheet on project %s")
                % project.name
            )

        quantity = tlines._get_invoiceable_qty_with_project_unit()
        vals = {
            "task_id": task.id,
            "product_id": project.product_id.id,
            "name": "[{}] {}".format(task.id, task.name),
            "subcontracted": False,
            "product_uom_id": project.uom_id.id,
            "price_unit": project.supplier_invoice_price_unit,
            "account_id": project.supplier_invoice_account_expense_id.id,
            "analytic_account_id": project.analytic_account_id.id,
            "quantity": quantity,
        }
        return line_obj.play_onchanges(vals, ["product_id", "product_uom_id"])

    def _add_update_invoice_line(self, task, tlines):
        inv_line = task.invoice_line_ids.filtered(
            lambda s: s.move_id == self.invoice_id
        )
        if inv_line:
            tlines |= inv_line.timesheet_line_ids
        vals = self._prepare_invoice_line(task, tlines)
        if not inv_line:
            self.invoice_id.write({"invoice_line_ids": [(0, 0, vals)]})
            inv_line = task.invoice_line_ids.filtered(
                lambda s: s.move_id == self.invoice_id
            )
        else:
            self.invoice_id.write(
                {"invoice_line_ids": [(0, 0, vals), (2, inv_line.id, 0)]}
            )
        tlines.write({"supplier_invoice_line_id": inv_line.id})

    def _get_invoice_vals(self):
        self.ensure_one()
        vals = {"partner_id": self.partner_id.id, "move_type": "in_invoice"}
        vals = self.env["account.move"].play_onchanges(vals, ["partner_id"])
        return vals

    def action_invoice(self):
        self.ensure_one()
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
        for task, tlines in self._get_task2tlines().items():
            self._add_update_invoice_line(task, tlines)

        # return the invoice view
        action = self.env.ref("account.action_move_in_invoice_type").sudo().read()[0]
        action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
        action["res_id"] = self.invoice_id.id
        return action
