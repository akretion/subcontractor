# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, exceptions, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    project_id = fields.Many2one("project.project", string="Project", index="btree")

    def _check_project_required_msg(self):
        self.ensure_one()
        company_cur = self.company_currency_id
        if company_cur.is_zero(self.debit) and company_cur.is_zero(self.credit):
            return None
        project_policy = self.account_id._get_project_policy()
        if project_policy == "always" and not self.project_id:
            return _(
                "Project policy is set to 'Always' with account "
                "'%(account)s' but the project is missing in "
                "the account move line with label '%(move)s'."
            ) % {
                "account": self.account_id.display_name,
                "move": self.name or "",
            }
        elif project_policy == "never" and (self.project_id):
            project = self.project_id
            return _(
                "Project policy is set to 'Never' with account "
                "'%(account)s' but the account move line with label '%(move)s' "
                "has an project '%(project_account)s'."
            ) % {
                "account": self.account_id.display_name,
                "move": self.name or "",
                "project_account": project.name,
            }
        elif (
            project_policy == "posted"
            and not self.project_id
            and self.move_id.state == "posted"
        ):
            return _(
                "Project policy is set to 'Posted moves' with "
                "account '%(account)s' but the project is missing "
                "in the account move line with label '%(move)s'."
            ) % {
                "account": self.account_id.display_name,
                "move": self.name or "",
            }
        return None

    @api.constrains("project_id", "account_id", "debit", "credit")
    def _check_project_required(self):
        for rec in self:
            message = rec._check_project_required_msg()
            if message:
                raise exceptions.ValidationError(message)
