# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    prepaid_countdown_journal_id = fields.Many2one(
        "account.journal",
        string="Prepaid Countdown Journal",
        related="company_id.prepaid_countdown_journal_id",
        readonly=False,
        help="Journal used to create the countdown entries for prepaid revenue",
    )
