# Copyright 2024 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    budget_ids = fields.One2many("project.budget", "project_id", string="Budgets")
    use_budget = fields.Boolean(related="partner_id.use_budget")

    current_budget_id = fields.Many2one(
        "project.budget", compute="_compute_current_budget_id"
    )
    current_budget_amount = fields.Float(
        related="current_budget_id.budget_amount", readonly=True
    )
    current_invoiced_amount = fields.Float(
        related="current_budget_id.invoiced_amount", readonly=True
    )
    current_to_invoice_amount = fields.Float(
        related="current_budget_id.to_invoice_amount", readonly=True
    )
    current_remaining_amount = fields.Float(
        related="current_budget_id.remaining_amount", readonly=True
    )
    current_remaining_budget = fields.Float(
        related="current_budget_id.remaining_budget", readonly=True
    )
    current_budget_amount_prorata = fields.Float(
        related="current_budget_id.budget_amount_prorata", readonly=True
    )
    current_budget_progress = fields.Float(
        related="current_budget_id.budget_progress", readonly=True
    )
    current_time_progress = fields.Float(
        related="current_budget_id.time_progress", readonly=True
    )

    def _compute_current_budget_id(self):
        for project in self:
            project.current_budget_id = project.budget_ids.filtered(
                lambda b: b.start_date <= fields.Date.today() <= b.end_date
            )
