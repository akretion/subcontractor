# Copyright 2024 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    budget_date = fields.Date(
        compute="_compute_budget_date",
        store=True,
        readonly=False,
    )
    use_budget = fields.Boolean(related="partner_id.use_budget")

    @api.depends("invoice_date")
    def _compute_budget_date(self):
        for move in self:
            if not move.budget_date:
                move.budget_date = move.invoice_date

    def _post(self, soft=True):
        for move in self:
            if move.use_budget:
                if move.invoice_line_ids.filtered(lambda line: not line.project_id):
                    raise UserError(
                        _(
                            "You can't post a move containing lines without project "
                            "for a customer with budget enabled."
                        )
                    )
        return super()._post(soft=soft)
