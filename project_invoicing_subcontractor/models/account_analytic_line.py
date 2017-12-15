# -*- coding: utf-8 -*-
# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    subcontractor_work_id = fields.Many2one('subcontractor.work')
    invoice_id = fields.Many2one(
        'account.invoice',
        related='subcontractor_work_id.invoice_line_id.invoice_id',
        store=True)
