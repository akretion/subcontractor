# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    prepaid_available_amount = fields.Monetary(compute="_compute_prepaid_amount")
    prepaid_total_amount = fields.Monetary(compute="_compute_prepaid_amount")

    def _compute_prepaid_amount(self):
        for partner in self:
            total_amount = 0
            available_amount = 0
            projects = self.env["project.project"].search(
                [
                    ("partner_id", "=", partner.id),
                    ("invoicing_mode", "=", "customer_prepaid"),
                ]
            )
            for project in projects:
                total_amount += project.prepaid_total_amount
                available_amount += project.prepaid_available_amount
            partner.prepaid_total_amount = total_amount
            partner.prepaid_available_amount = available_amount

    def action_partner_prepaid_move_line(self):
        self.ensure_one()
        action = self.env.ref("account.action_account_moves_all_tree").sudo().read()[0]
        projects = self.env["project.project"].search(
            [("partner_id", "=", self.id), ("invoicing_mode", "=", "customer_prepaid")]
        )
        move_lines = paid_lines = self.env["account.move.line"]
        for project in projects:
            (
                project_move_lines,
                project_paid_lines,
            ) = project.analytic_account_id._prepaid_move_lines()
            move_lines |= project_move_lines
            paid_lines |= project_paid_lines
        if self.env.context.get("prepaid_is_paid"):
            move_lines = paid_lines
        action["domain"] = [("id", "in", move_lines.ids)]
        action["context"] = {
            "search_default_group_by_account": 1,
            "create": False,
            "edit": False,
            "delete": False,
        }
        return action
