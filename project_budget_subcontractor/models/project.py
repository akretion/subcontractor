# Copyright 2024 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    budget_ids = fields.One2many("project.budget", "project_id", string="Budgets")
    use_budget = fields.Boolean(related="partner_id.use_budget")

    current_budget_id = fields.Many2one(
        "project.budget", compute="_compute_current_budget_id"
    )
    current_budget_amount = fields.Float(
        string="Budget Amount", compute="_compute_current_budget_id"
    )
    current_invoiced_amount = fields.Float(
        string="Invoiced Amount", compute="_compute_current_budget_id"
    )
    current_to_invoice_amount = fields.Float(
        string="To Invoice Amount", compute="_compute_current_budget_id"
    )
    current_remaining_amount = fields.Float(
        string="Remaining Amount", compute="_compute_current_budget_id"
    )
    current_remaining_budget = fields.Float(
        string="Remaining Budget", compute="_compute_current_budget_id"
    )
    current_budget_amount_prorata = fields.Float(
        string="Budget Amount Prorata", compute="_compute_current_budget_id"
    )
    current_budget_progress = fields.Float(
        string="Budget Progress", compute="_compute_current_budget_id"
    )
    current_time_progress = fields.Float(
        string="Time Progress", compute="_compute_current_budget_id"
    )

    def _compute_current_budget_id(self):
        for project in self:
            current = project.current_budget_id = project.budget_ids.filtered(
                lambda b: b.start_date <= fields.Date.today() <= b.end_date
            )

            if current:
                project.current_budget_amount = current.budget_amount
                project.current_invoiced_amount = current.invoiced_amount
                project.current_to_invoice_amount = current.to_invoice_amount
                project.current_remaining_amount = current.remaining_amount
                project.current_remaining_budget = current.remaining_budget
                project.current_budget_amount_prorata = current.budget_amount_prorata
                project.current_budget_progress = current.budget_progress
                project.current_time_progress = current.time_progress
            else:
                project.current_budget_amount = False
                project.current_invoiced_amount = False
                project.current_to_invoice_amount = False
                project.current_remaining_amount = False
                project.current_remaining_budget = False
                project.current_budget_amount_prorata = False
                project.current_budget_progress = False
                project.current_time_progress = False
