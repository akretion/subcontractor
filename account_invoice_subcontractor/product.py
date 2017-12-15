# coding: utf-8
# © 2015 Akretion
#   @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = "product.template"

    no_commission = fields.Boolean(
        help="This product has no commission for subcontractor work.")
    subcontracted = fields.Boolean(
        company_dependent=True,
        help="This product is subcontracted, and so the subcontractor work "
             "will be required on the invoice")
