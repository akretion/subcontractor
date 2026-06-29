# Copyright 2017 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class AccountUpdateLockDate(models.TransientModel):
    _inherit = "account.update.lock_date"

    cutoff_lock_date = fields.Date(
        help="Start/End dates on subcontractor invoice lines will never be set before "
        "this date."
    )

    @api.model
    def default_get(self, field_list):
        res = super().default_get(field_list)
        company = self.env.company
        res["cutoff_lock_date"] = company.cutoff_lock_date
        return res

    def execute(self):
        res = super().execute()
        today = fields.Date.context_today(self)
        if self.cutoff_lock_date and self.cutoff_lock_date > today:
            raise UserError(
                self.env._(
                    "You tried to set Cutoff lock date to %(date)s, "
                    "but it is in the future.",
                    date=format_date(self.env, self.cutoff_lock_date),
                )
            )
        self.company_id.sudo().cutoff_lock_date = self.cutoff_lock_date
        return res
