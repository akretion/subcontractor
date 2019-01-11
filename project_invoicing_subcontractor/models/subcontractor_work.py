# -*- coding: utf-8 -*-
# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import fields, models


class SubcontractorWork(models.Model):
    _inherit = 'subcontractor.work'

    timesheet_line_ids = fields.One2many(
        'account.analytic.line',
        'subcontractor_work_id',
        string="Timesheet Line")
