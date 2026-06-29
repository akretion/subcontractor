# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    commission_rate = fields.Float(
        help="Rate in % for the commission on subcontractor work", default=11.00
    )
    cutoff_lock_date = fields.Date(
        help="Start/End dates on subcontractor invoice lines will never be set before "
        "this date."
    )

    def _get_commission_rate(self):
        self.ensure_one()
        return self.commission_rate / 100.0
