# -*- coding: utf-8 -*-
###############################################################################
#
#   account_invoice_subcontractor for OpenERP
#   Copyright (C) 2015-TODAY Akretion <http://www.akretion.com>.
#   @author Sébastien BEAU <sebastien.beau@akretion.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

from openerp import models, fields, api
from openerp.osv import fields as old_fields


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    _map_type = {
        'in_invoice': 'supplier_invoice_line_id',
        'out_invoice': 'subcontractor_invoice_line_id',
    }

    def _get_line_from_work(self, cr, uid, ids, context=None):
        res = set()
        for work in self.browse(cr, uid, ids, context=context):
            if work.supplier_invoice_line_id:
                res.add(work.supplier_invoice_line_id.id)
            if work.subcontractor_invoice_line_id:
                res.add(work.subcontractor_invoice_line_id.id)
        return list(res)

    def _get_line_from_invoice(self, cr, uid, ids, context=None):
        return self.pool['account.invoice.line'].search(
            cr, uid, [('invoice_id', 'in', ids)], context=context)

    def _get_work_invoiced(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            field = self._map_type.get(line.invoice_id.type, False)
            if field:
                work_obj = self.pool['subcontractor.work']
                work_ids = work_obj.search(
                    cr, uid, [[field, '=', line.id]], context=context)
                if work_ids:
                    res[line.id] = work_ids[0]
        return res

    def _set_work_invoiced(self, cr, uid, ids, name, value, arg, context=None):
        if not value:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context=context):
            field = self._map_type[line.invoice_id.type]
            work_obj = self.pool['subcontractor.work']
            work_obj.write(cr, 1, [value], {field: line.id}, context=context)
        return True

    _columns = {
        'subcontractor_work_invoiced_id': old_fields.function(
            _get_work_invoiced,
            fnct_inv=_set_work_invoiced,
            type="many2one", copy=False,
            relation='subcontractor.work',
            string='Invoiced Work',
            store={
                'subcontractor.work': (
                    _get_line_from_work,
                    ['supplier_invoice_line_id',
                     'subcontractor_invoice_line_id'],
                    10),
                'account.invoice': (_get_line_from_invoice, ['type'], 20),
                'account.invoice.line': (
                    lambda self, cr, uid, ids, c=None: ids,
                    ['invoice_id'],
                    30)
            }),
    }

    subcontracted = fields.Boolean()
    subcontractor_work_ids = fields.One2many(
        'subcontractor.work',
        'invoice_line_id',
        string='Subcontractor Work')
    invalid_work_amount = fields.Boolean(
        compute='_is_work_amount_invalid',
        string='Work Amount Invalid',
        store=True)

    @api.multi
    def product_id_change(self, product, uom_id, qty=0, name='',
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

    @api.depends(
        'invoice_id', 'invoice_id.type', 'invoice_id.company_id',
        'invoice_id.partner_id', 'subcontractor_work_invoiced_id',
        'subcontractor_work_invoiced_id.cost_price', 'price_subtotal',
        'subcontracted',
    )
    @api.multi
    def _is_work_amount_invalid(self):
        print 'start valid'
        for line in self:
            if line.invoice_id.type in ['out_invoice', 'in_invoice']:
                if not line.subcontracted:
                    line.invalid_work_amount = False
                else:
                    if line.invoice_id.type == 'in_invoice':
                        line.invalid_work_amount = abs(
                            line.subcontractor_work_invoiced_id.cost_price
                            - line.price_subtotal) > 0.01
                    else:
                        # TODO FIXME
                        if line.invoice_id.company_id.id != 1:
                            # this mean Akretion
                            if line.invoice_id.partner_id.id == 1:
                                line.invalid_work_amount = abs(
                                    (line.subcontractor_work_invoiced_id
                                     .cost_price - line.price_subtotal)) > 0.01
                            else:
                                line.invalid_work_amount = False
                        else:
                            subtotal = sum([
                                work.sale_price for work in (
                                    line.subcontractor_work_ids)])
                            line.invalid_work_amount = abs(
                                subtotal - line.price_subtotal) > 0.01
            else:
                line.invalid_work_amount = False
        print 'end valid'


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    to_pay = fields.Boolean(compute='_get_to_pay', store=True)
    invalid_work_amount = fields.Boolean(
        compute='_is_work_amount_valid', store=True)

    @api.depends(
        'invoice_line',
        'invoice_line.subcontractor_work_invoiced_id',
        'invoice_line.subcontractor_work_invoiced_id.state')
    @api.multi
    def _get_to_pay(self):
        for invoice in self:
            if invoice.type == 'in_invoice':
                if invoice.state == 'paid':
                    invoice.to_pay = False
                else:
                    invoice.to_pay = all([
                        line.subcontractor_work_invoiced_id.state == 'paid'
                        for line in invoice.invoice_line])

    @api.depends('invoice_line', 'invoice_line.invalid_work_amount')
    @api.multi
    def _is_work_amount_valid(self):
        for invoice in self:
            invoice.invalid_work_amount = any([
                line.invalid_work_amount
                for line in invoice.invoice_line])

    @api.model
    def _prepare_invoice_line_data(self, line_data, line):
        res = super(AccountInvoice, self)._prepare_invoice_line_data(
            line_data, line)
        res['subcontractor_work_invoiced_id'] =\
            line.subcontractor_work_invoiced_id.id
        return res
