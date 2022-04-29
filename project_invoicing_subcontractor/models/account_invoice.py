# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)


from odoo import api, fields, models

import odoo.addons.decimal_precision as dp


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    task_id = fields.Many2one("project.task")
    task_stage_id = fields.Many2one(
        "project.task.type", related="task_id.stage_id", store=True
    )
    timesheet_line_ids = fields.One2many(
        "account.analytic.line", "invoice_line_id", "Timesheet Line"
    )
    timesheet_error = fields.Char(compute="_compute_timesheet_qty", store=True)
    timesheet_qty = fields.Float(
        digits=dp.get_precision("Product Unit of Measure"),
        compute="_compute_timesheet_qty",
        store=True,
    )

    @api.depends(
        "timesheet_line_ids.discount", "timesheet_line_ids.unit_amount", "quantity"
    )
    def _compute_timesheet_qty(self):
        for record in self:
            record.timesheet_qty = record.timesheet_line_ids._get_invoiceable_qty_with_unit(
                record.uom_id
            )
            if abs(record.timesheet_qty - record.quantity) > 0.001:
                record.timesheet_error = u"⏰ %s" % record.timesheet_qty

    def open_task(self):
        self.ensure_one()
        action = self.env.ref("project.action_view_task").read()[0]
        action.update(
            {
                "res_id": self.task_id.id,
                "views": [x for x in action["views"] if x[1] == "form"],
            }
        )
        return action


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    def action_view_subcontractor(self):
        self.ensure_one()
        action = self.env.ref(
            "account_invoice_subcontractor.action_subcontractor_work"
        ).read()[0]
        action["context"] = {
            "search_default_invoice_id": self.id,
            "search_default_subcontractor": 1,
        }
        return action

    def action_view_analytic_line(self):
        self.ensure_one()
        action = self.env.ref("hr_timesheet.act_hr_timesheet_line").read()[0]
        action["domain"] = [("invoice_id", "=", self.id)]
        return action
