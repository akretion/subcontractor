# Copyright 2024 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProjectBudget(models.Model):
    _name = "project.budget"
    _description = "Project Budget"

    name = fields.Char(required=True)
    project_id = fields.Many2one("project.project", required=True, tracking=True)
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    budget_amount = fields.Float(required=True, tracking=True)

    invoiced_amount = fields.Float(compute="_compute_invoiced_amount")
    to_invoice_amount = fields.Float(compute="_compute_to_invoice_amount")
    remaining_amount = fields.Float(compute="_compute_remaining_amount")
    remaining_budget = fields.Float(compute="_compute_remaining_budget")
    budget_amount_prorata = fields.Float(
        compute="_compute_budget_amount_prorata", string="Time Prorata"
    )
    budget_progress = fields.Float(compute="_compute_budget_progress")
    time_progress = fields.Float(compute="_compute_time_progress")

    @api.depends("budget_amount", "start_date", "end_date")
    def _compute_budget_amount_prorata(self):
        today = fields.Date.today()
        for budget in self:
            if (
                not budget.start_date
                or not budget.end_date
                or budget.end_date < today
                or budget.start_date > today
            ):
                budget.budget_amount_prorata = 0.0
                continue
            total_days = (budget.end_date - budget.start_date).days + 1
            remaining_days = (budget.end_date - today).days + 1
            budget.budget_amount_prorata = (
                budget.budget_amount * remaining_days / total_days
            )

    @api.depends("project_id.timesheet_ids.invoice_line_id", "start_date", "end_date")
    def _compute_invoiced_amount(self):
        for budget in self:
            if not budget.start_date or not budget.end_date:
                budget.invoiced_amount = 0.0
                continue
            # FIXME: There's also a move_id on account.analytic.line
            move_lines = budget.project_id.timesheet_ids.invoice_line_id.filtered(
                lambda ml: ml.parent_state == "posted"
                and ml.date >= budget.start_date
                and ml.date <= budget.end_date
            )
            budget.invoiced_amount = sum(move_lines.mapped("price_subtotal"))

    @api.depends("project_id.timesheet_ids", "start_date", "end_date")
    def _compute_to_invoice_amount(self):
        for budget in self:
            if not budget.start_date or not budget.end_date:
                budget.to_invoice_amount = 0.0
                continue
            move_lines = budget.project_id.timesheet_ids.filtered(
                lambda ml: (
                    not ml.invoice_line_id or ml.invoice_line_id.parent_state == "draft"
                )
                and ml.date >= budget.start_date
                and ml.date <= budget.end_date
            )
            budget.to_invoice_amount = -sum(
                budget.project_id.convert_hours_to_days(
                    ml.unit_amount * (1 - ml.discount / 100.0)
                )
                * ml.amount
                for ml in move_lines
            )

    @api.depends(
        "project_id.task_ids", "project_id.price_unit", "start_date", "end_date"
    )
    def _compute_remaining_amount(self):
        for budget in self:
            if not budget.start_date or not budget.end_date:
                budget.remaining_amount = 0.0
                continue
            remaining_days = sum(
                budget.project_id.task_ids.filtered(
                    lambda t: t.date_start
                    and t.date_end
                    and t.date_start.date() >= budget.start_date
                    and t.date_end.date() <= budget.end_date
                    and not t.stage_id.is_closed
                ).mapped("remaining_days")
            )
            budget.remaining_amount = remaining_days * budget.project_id.price_unit

    @api.depends("budget_amount", "invoiced_amount", "to_invoice_amount")
    def _compute_remaining_budget(self):
        for budget in self:
            budget.remaining_budget = budget.budget_amount - (
                budget.invoiced_amount + budget.to_invoice_amount
            )

    @api.depends("budget_amount", "invoiced_amount", "to_invoice_amount")
    def _compute_budget_progress(self):
        for budget in self:
            if not budget.budget_amount:
                budget.budget_progress = 0.0
                continue
            budget.budget_progress = (
                budget.invoiced_amount + budget.to_invoice_amount
            ) / budget.budget_amount

    @api.depends("start_date", "end_date")
    def _compute_time_progress(self):
        for budget in self:
            if not budget.start_date or not budget.end_date:
                budget.time_progress = 0.0
                continue
            today = fields.Date.today()
            total_days = (budget.end_date - budget.start_date).days + 1
            spent_days = (today - budget.start_date).days + 1
            budget.time_progress = spent_days / total_days