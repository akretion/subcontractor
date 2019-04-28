# -*- coding: utf-8 -*-
# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import odoo.addons.decimal_precision as dp
from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    subcontractor_work_id = fields.Many2one('subcontractor.work')
    invoice_id = fields.Many2one(
        'account.invoice',
        related='subcontractor_work_id.invoice_line_id.invoice_id',
        store=True,
        readonly=True)
    task_stage_id = fields.Many2one(
        'project.task.type',
        related='task_id.stage_id',
        store=True)
    invoiceable = fields.Boolean(
        compute='_compute_invoiceable',
        store=True)
    discount = fields.Float(digits=dp.get_precision('Discount'))

    def is_invoiceable(self):
        self.ensure_one()
        invoicing = self.task_id.invoicing
        if self.discount == 100:
            return False
        elif invoicing == 'progressive':
            return True
        elif invoicing == 'none':
            return False
        elif invoicing == 'finished':
            return self.task_stage_id == self.project_id.invoicing_stage_id

    @api.depends(
        'discount',
        'task_id.stage_id',
        'task_id.invoicing',
        'project_id.invoicing_stage_id')
    def _compute_invoiceable(self):
        for record in self:
            record.invoiceable = record.is_invoiceable()

    def _get_invoiceable_qty_with_project_unit(self):
        return self._get_invoiceable_qty_with_unit(self.project_id.uom_id)

    def _get_invoiceable_qty_with_unit(self, uom):
        self.ensure_one()
        qty = self.unit_amount * (1- self.discount/100.)
        hours_uom = self.env.ref('product.product_uom_hour')
        if uom == hours_uom:
            return qty
        else:
            return hours_uom._compute_quantity(qty, uom)