# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models


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


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_view_subcontractor(self):
        self.ensure_one()
        action = (
            self.env.ref("account_invoice_subcontractor.action_subcontractor_work")
            .sudo()
            .read()[0]
        )
        action["context"] = {
            "search_default_invoice_id": self.id,
            "search_default_subcontractor": 1,
        }
        return action

    def action_view_analytic_line(self):
        self.ensure_one()
        action = self.env.ref("hr_timesheet.act_hr_timesheet_line").sudo().read()[0]
        action["domain"] = [("invoice_id", "=", self.id)]
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
