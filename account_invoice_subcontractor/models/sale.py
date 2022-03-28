# © 2015 Akretion
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, qty):
        vals = super()._prepare_invoice_line(qty)
        vals["subcontracted"] = self.product_id.subcontracted or False
        return vals
