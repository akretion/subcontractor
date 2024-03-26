# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    commission_rate = fields.Float(
        related="company_id.commission_rate",
        readonly=False,
        help="Rate in % for the commission on subcontractor work",
    )
