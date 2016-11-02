# -*- coding: utf-8 -*-
# © 2016 Akretion (http://www.akretion.com)
# Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import api, fields, models


class HrAnalyticTimesheet(models.Model):
    _inherit = 'hr.analytic.timesheet'

    subcontractor_work_id = fields.Many2one('subcontractor.work')
    invoice_id = fields.Many2one(
        'account.invoice',
        related='subcontractor_work_id.invoice_line_id.invoice_id',
        store=True)
