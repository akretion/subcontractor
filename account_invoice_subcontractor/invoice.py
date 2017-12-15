# coding: utf-8
# © 2015 Akretion
#   @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api
# from odoo.osv import fields as old_fields


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    _map_type = {
        'in_invoice': 'supplier_invoice_line_id',
        'out_invoice': 'subcontractor_invoice_line_id',
    }

    subcontracted = fields.Boolean()
    subcontractor_work_ids = fields.One2many(
        'subcontractor.work',
        'invoice_line_id',
        string='Subcontractor Work')
    subcontractor_work_invoiced_id = fields.Many2one(
        'subcontractor.work',
        compute='_get_work_invoiced',
        inverse='_set_work_invoiced',
        string='Invoiced Work',
        store=True,
        _prefetch=False)
    invalid_work_amount = fields.Boolean(
        compute='_is_work_amount_invalid',
        string='Work Amount Invalid',
        store=True)

    @api.multi
    def product_id_change(
            self, product, uom_id, qty=0, name='',
            type='out_invoice', partner_id=False, fposition_id=False,
            price_unit=False, currency_id=False, company_id=None):
        res = super(AccountInvoiceLine, self).product_id_change(
            product, uom_id, qty=qty, name=name,
            type=type, partner_id=partner_id, fposition_id=fposition_id,
            price_unit=price_unit, currency_id=currency_id,
            company_id=company_id)
        product = self.env['product.product'].browse(product)
        res['value']['subcontracted'] = product.subcontracted
        return res

    @api.depends('invoice_id', 'invoice_id.type')
    @api.multi
    def _get_work_invoiced(self):
        for line in self:
            field = self._map_type.get(line.invoice_id.type, False)
            if field:
                work_obj = self.env['subcontractor.work']
                work = work_obj.search([[field, '=', line.id]])
                line.subcontractor_work_invoiced_id = work.id

    @api.multi
    def _set_work_invoiced(self):
        for line in self:
            work = line.subcontractor_work_invoiced_id
            if work:
                field = self._map_type.get(line.invoice_id.type, False)
                if field:
                    work.sudo().write({field: line.id})

    @api.depends(
        'invoice_id', 'invoice_id.type', 'invoice_id.company_id',
        'invoice_id.partner_id', 'subcontractor_work_invoiced_id',
        'subcontractor_work_invoiced_id.cost_price', 'price_subtotal',
        'subcontracted',
    )
    @api.multi
    def _is_work_amount_invalid(self):
        for line in self:
            if line.invoice_id.type in ['out_invoice', 'in_invoice']:
                if line.subcontracted:
                    if line.invoice_id.type == 'in_invoice':
                        line.invalid_work_amount = abs(
                            line.subcontractor_work_invoiced_id.cost_price -
                            line.price_subtotal) > 0.1
                    else:
                        # TODO FIXME
                        if line.invoice_id.company_id.id != 1:
                            # this mean Akretion
                            if line.invoice_id.partner_id.id == 1:
                                line.invalid_work_amount = abs(
                                    (line.subcontractor_work_invoiced_id
                                     .cost_price - line.price_subtotal)) > 0.1
                        else:
                            subtotal = sum([
                                work.sale_price for work in (
                                    line.subcontractor_work_ids)])
                            line.invalid_work_amount = abs(
                                subtotal - line.price_subtotal) > 0.01


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    to_pay = fields.Boolean(
        compute='_get_to_pay', store=True, compute_sudo=True)
    invalid_work_amount = fields.Boolean(
        compute='_is_work_amount_valid', store=True)

    @api.depends(
        'invoice_line_ids',
        'invoice_line_ids.subcontractor_work_invoiced_id',
        'invoice_line_ids.subcontractor_work_invoiced_id.state')
    @api.multi
    def _get_to_pay(self):
        for invoice in self:
            if invoice.type == 'in_invoice':
                if invoice.state == 'paid':
                    invoice.to_pay = False
                else:
                    invoice.to_pay = all([
                        line.subcontractor_work_invoiced_id.state == 'paid'
                        for line in invoice.invoice_line_ids])

    @api.depends('invoice_line_ids', 'invoice_line_ids.invalid_work_amount')
    @api.multi
    def _is_work_amount_valid(self):
        for invoice in self:
            invoice.invalid_work_amount = any([
                line.invalid_work_amount
                for line in invoice.invoice_line_ids])

    @api.model
    def _prepare_invoice_line_data(self, line_data, line):
        res = super(AccountInvoice, self)._prepare_invoice_line_data(
            line_data, line)
        res['subcontractor_work_invoiced_id'] =\
            line.subcontractor_work_invoiced_id.id
        return res
