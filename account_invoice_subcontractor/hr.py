# coding: utf-8
# © 2015 Akretion
#   @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _get_subcontractor_type(self):
        return [
            ('trainee', 'Trainee'),
            ('internal', 'Internal'),
            ('external', 'External')
        ]

    subcontractor_company_id = fields.Many2one(
        'res.company',
        string='Subcontractor Company')
    subcontractor_type = fields.Selection(
        string='Subcontractor Type',
        selection='_get_subcontractor_type',
        required=True)
    commission_rate = fields.Float(
        help="Rate in % for the commission on subcontractor work",
        default=10.00)
