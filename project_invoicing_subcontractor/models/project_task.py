# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    invoiceable_hours = fields.Float(compute="_compute_invoiceable", store=True)
    invoiceable_days = fields.Float(compute="_compute_invoiceable", store=True)
    invoice_line_ids = fields.One2many("account.move.line", "task_id", "Invoice Line")

    @api.depends("timesheet_ids.discount", "timesheet_ids.unit_amount")
    def _compute_invoiceable(self):
        for record in self:
            total = 0
            for line in record.timesheet_ids:
                total += line.unit_amount * (1 - line.discount / 100.0)
            record.invoiceable_hours = total
            record.invoiceable_days = record.project_id.convert_hours_to_days(total)

    # TODO we should move this in a generic module
    # changing the project on the task should be propagated
    # on the analytic line to avoid issue during invoicing
    def write(self, vals):
        res = super().write(vals)
        if "project_id" in vals:
            if not vals["project_id"]:
                raise UserError(
                    _(
                        "The project can not be removed, "
                        "please remove the timesheet first"
                    )
                )
            else:
                project = self.env["project.project"].browse(vals["project_id"])
                vals = {
                    "project_id": project.id,
                    "account_id": project.analytic_account_id.id,
                }
            self.mapped("timesheet_ids").write(vals)
        return res
