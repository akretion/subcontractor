# Copyright 2024 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProjectBudget(models.Model):
    _name = "project.budget"
    _description = "Project Budget"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True)
    project_id = fields.Many2one("project.project", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", related="project_id.partner_id", store=True
    )
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    budget_amount = fields.Float(required=True, tracking=True)

    invoiced_amount = fields.Float(
        compute="_compute_invoiced_amount", string="Montant Facturé"
    )
    to_invoice_amount = fields.Float(
        compute="_compute_to_invoice_amount", string="Montant à Facturer"
    )
    remaining_amount = fields.Float(
        compute="_compute_remaining_amount", string="Montant Restant Estimé"
    )
    remaining_budget = fields.Float(
        compute="_compute_remaining_budget", string="Budget Restant"
    )
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
                or budget.start_date > today
            ):
                budget.budget_amount_prorata = 0.0
                continue

            if budget.end_date < today:
                budget.budget_amount_prorata = budget.budget_amount
                continue

            total_days = (budget.end_date - budget.start_date).days + 1
            spent_days = (today - budget.start_date).days + 1
            budget.budget_amount_prorata = (
                budget.budget_amount * spent_days / total_days
            )

    @api.depends("project_id.timesheet_ids.invoice_line_id", "start_date", "end_date")
    def _compute_invoiced_amount(self):
        for budget in self:
            if not budget.start_date or not budget.end_date:
                budget.invoiced_amount = 0.0
                continue
            move_lines = (
                budget.project_id.analytic_account_id.invoice_line_ids.filtered(
                    lambda ml, budget=budget: ml.parent_state == "posted"
                    and ml.move_id.budget_date
                    and ml.move_id.budget_date >= budget.start_date
                    and ml.move_id.budget_date <= budget.end_date
                )
            )
            budget.invoiced_amount = sum(move_lines.mapped("price_subtotal"))

    @api.depends("project_id.timesheet_ids", "start_date", "end_date")
    def _compute_to_invoice_amount(self):
        today = fields.Date.today()
        data = self.env["account.analytic.line"].read_group(
            [
                ("project_id", "in", self.project_id.ids),
                "|",
                ("invoice_line_id", "=", False),
                ("invoice_line_id.parent_state", "=", "draft"),
            ],
            ["invoiceable_amount:sum"],
            ["project_id"],
        )
        p2hours = {item["project_id"][0]: item["invoiceable_amount"] for item in data}
        for budget in self:
            if not budget.start_date or not budget.end_date or budget.end_date < today:
                budget.to_invoice_amount = 0.0
                continue
            project = budget.project_id
            if isinstance(project.id, models.NewId):
                project = project._origin
            budget.to_invoice_amount = (
                project.convert_hours_to_days(p2hours[project.id]) * project.price_unit
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
                    lambda t, budget=budget: t.planned_date_start
                    and t.planned_date_end
                    and t.planned_date_start.date() >= budget.start_date
                    and t.planned_date_end.date() <= budget.end_date
                    and not t.is_closed
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
