# -*- coding: utf-8 -*-
# © 2016 Akretion (http://www.akretion.com)
# Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import api, fields, models


class SubcontractorWork(models.Model):
    _inherit = 'subcontractor.work'

    timesheet_line_ids = fields.One2many(
        'hr.analytic.timesheet',
        'subcontractor_work_id',
        string="Timesheet Line")
