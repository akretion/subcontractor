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
from openerp import SUPERUSER_ID


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    # TODO migrate not complete
    # @api.multi
    # def _get_work_invoiced(self):
    #     line_type = field_name.split('_')[0]
    #     work_obj = self.pool['subcontractor.work']
    #     for line in self:
    #         work_ids = work_obj.search([
    #             ['%s_invoice_line_id' % line_type, '=', line.id]])
    #         line.subcontractor_work_invoiced_id = work_ids and work_ids[0]
    # or None
    #         line.supplier_work_invoiced_id = work_ids and work_ids[0] or None

    # TODO migrate not complete
    # @api.multi
    # def _set_work_invoiced(self):
    #     work_obj = self.pool['subcontractor.work']
    #     line_type = field_name.split('_')[0]
    #     line_key = '%s_invoice_line_id' % line_type
    #     work_ids = work_obj.search([[line_key, '=', self.id]])
    #     if work_ids:
    #         work_obj.sudo().write(value, {line_key: False})
    #     if value:
    #         work_obj.sudo().write(value, {line_key: self.id})

    def _get_work_invoiced(self, cr, uid, ids, field_name, args, context=None):
        line_type = field_name.split('_')[0]
        result = {}
        work_obj = self.pool['subcontractor.work']
        for line in self.browse(cr, uid, ids, context=context):
            work_id = work_obj.search(cr, uid, [
                ['%s_invoice_line_id' % line_type, '=', line.id]],
                context=context)
            result[line.id] = work_id and work_id[0] or None
        return result

    def _set_work_invoiced(
            self, cr, uid, line_id, field_name, value, args, context=None):
        work_obj = self.pool['subcontractor.work']
        line_type = field_name.split('_')[0]
        line_key = '%s_invoice_line_id' % line_type
        work_id = work_obj.search(cr, uid, [
            [line_key, '=', line_id]],
            context=context)
        if work_id:
            work_obj.write(
                cr, SUPERUSER_ID, value, {line_key: False}, context=context)
        if value:
            work_obj.write(
                cr, SUPERUSER_ID, value, {line_key: line_id}, context=context)
        return True

    @api.multi
    def _is_work_amount_invalid(self):
        for line in self:
            if line.invoice_id.type in ['out_invoice', 'in_invoice']:
                if line.no_subcontractor_work:
                    line.invalid_work_amount = False
                else:
                    if line.invoice_id.type == 'in_invoice':
                        subtotal = (line.supplier_work_invoiced_id.
                                    cost_price or 0)
                        line.invalid_work_amount = abs(
                            subtotal - line.price_subtotal) > 0.01
                    else:
                        #TODO FIXME
                        if line.invoice_id.company_id.id != 1:
                            #this mean Akretion
                            if line.invoice_id.partner_id.id == 1:
                                subtotal = (line.
                                            subcontractor_work_invoiced_id.
                                            cost_price or 0)
                                line.invalid_work_amount = abs(
                                    subtotal - line.price_subtotal) > 0.01
                            else:
                                line.invalid_work_amount = False
                        else:
                            subtotal = sum([
                                work.sale_price for work in (
                                    line.subcontractor_work_ids)])
                            print subtotal, line.price_subtotal
                            line.invalid_work_amount = abs(
                                subtotal - line.price_subtotal) > 0.01
            else:
                line.invalid_work_amount = False

    subcontractor_work_ids = fields.One2many('subcontractor.work',
                                             'invoice_line_id',
                                             string='Subcontractor Work')
    subcontractor_work_invoiced_id = fields.Many2one(
        'subcontractor.work',
        compute='_get_work_invoiced',
        inverse='_set_work_invoiced',
        string='Invoiced Work')
    supplier_work_invoiced_id = fields.Many2one(
        'subcontractor.work',
        compute='_get_work_invoiced',
        inverse='_set_work_invoiced',
        string='Invoiced Work')
    invalid_work_amount = fields.Boolean(compute='_is_work_amount_invalid',
                                         string='Work Amount Invalid')
    no_subcontractor_work = fields.Boolean(
        string='No Subcontractor work',
        help=('This analytic account is incompatible with the workitem'
              'If you tick this box the workitem will'
              'be invisible on the invoice'))

    @api.multi
    def on_analytic_account_change(self, account_analytic_id):
        analytic_obj = self.pool['account.analytic.account']
        no_subcontractor_work = False
        if account_analytic_id:
            account = analytic_obj.browse(account_analytic_id)
            no_subcontractor_work = account.no_subcontractor_work
        return {'value': {'no_subcontractor_work': no_subcontractor_work}}


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def _get_to_pay(self):
        for invoice in self:
            if invoice.state == 'paid':
                invoice.to_pay = False
            else:
                invoice.to_pay = all([
                    (line.supplier_work_invoiced_id.state == 'paid'
                     for line in invoice.invoice_line)])

    @api.multi
    def _is_work_amount_valid(self):
        for invoice in self:
            invoice.invalid_work_amount = any([
                (line.invalid_work_amount
                 for line in invoice.invoice_line)])

    to_pay = fields.Boolean(compute='_get_to_pay', string='To Paid')
    invalid_work_amount = fields.Boolean(compute='_is_work_amount_valid',
                                         string='Work Amount Invalid')

    @api.model
    def _prepare_intercompany_line(self, line, *args, **kwargs):
        res = super(AccountInvoice, self)._prepare_intercompany_line(
            line, *args, **kwargs)
        res['supplier_work_invoiced_id'] = (
            line.subcontractor_work_invoiced_id.id)
        return res


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    no_subcontractor_work = fields.Boolean(
        string='No Subcontractor work',
        help=('This analytic account is incompatible with the '
              'workitem. If you tick this box the workitem '
              'will be invisible on the invoice'))
