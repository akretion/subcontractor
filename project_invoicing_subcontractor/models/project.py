# -*- coding: utf-8 -*-
# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    invoicing_stage_id = fields.Many2one(
        'project.task.type',
        'Invoicing Stage')
    product_id = fields.Many2one(
        'product.product',
        'Product')
    uom_id = fields.Many2one(
        'product.uom',
        'Unit')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    invoicing = fields.Selection([
        ('progressive', 'Progressive'),
        ('none', 'None'),
        ('finished', 'Finished'),
        ], default='finished',
        )
    invoiceable_hours = fields.Float(
        compute='_compute_invoiceable_hours',
        store=True)

    @api.depends('timesheet_ids.discount', 'timesheet_ids.unit_amount')
    def _compute_invoiceable_hours(self):
        for record in self:
            total = 0
            for line in record.timesheet_ids:
                total += line.unit_amount * (1 - line.discount / 100.)
            record.invoiceable_hours = total
