# -*- coding: utf-8 -*-
###############################################################################
#
#   account_invoice_subcontractor for OpenERP
#   Copyright (C) 2013-TODAY Akretion <http://www.akretion.com>.
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

from openerp.osv import orm, fields
from openerp import SUPERUSER_ID

class account_invoice_line(orm.Model):
    _inherit = "account.invoice.line"

    def _get_work_invoiced(self, cr, uid, ids, field_name, args, context=None):
        line_type = field_name.split('_')[0]
        result = {}
        work_obj = self.pool['subcontractor.work']
        for line in self.browse(cr, uid, ids, context=context):
            work_id = work_obj.search(cr, uid, [
                        ['%s_invoice_line_id'%line_type, '=', line.id]],
                        context=context)
            result[line.id] = work_id and work_id[0] or None
        return result

    def _set_work_invoiced(self, cr, uid, line_id, field_name, value, args, context=None):
        work_obj = self.pool['subcontractor.work']
        line_type = field_name.split('_')[0]
        line_key = '%s_invoice_line_id'%line_type
        work_id = work_obj.search(cr, uid, [
                        [line_key, '=', line_id]],
                        context=context)
        if work_id:
            work_obj.write(cr, SUPERUSER_ID, value, {line_key: False}, context=context)
        if value:
            work_obj.write(cr, SUPERUSER_ID, value, {line_key: line_id}, context=context)
        return True

    def _is_work_amount_invalid(self, cr, uid, ids, field_name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.invoice_id.type in ['out_invoice', 'in_invoice']:
                if line.no_subcontractor_work:
                    result[line.id] = False
                else:
                    if line.invoice_id.type == 'in_invoice':
                        subtotal = line.supplier_work_invoiced_id.cost_price or 0
                        result[line.id] = abs(subtotal - line.price_subtotal) > 0.01
                    else:
                        #TODO FIXME
                        if line.invoice_id.company_id.id != 1:
                            if line.invoice_id.partner_id.id == 1:#this mean Akretion
                                subtotal = line.subcontractor_work_invoiced_id.cost_price or 0
                                result[line.id] = abs(subtotal - line.price_subtotal) > 0.01
                            else:
                                result[line.id]=False
                        else:
                            subtotal = sum([work.sale_price for work in line.subcontractor_work_ids])
                            print subtotal, line.price_subtotal
                            result[line.id] = abs(subtotal - line.price_subtotal) > 0.01
            else:
                result[line.id] = False
        return result


    _columns = {
        'subcontractor_work_ids': fields.one2many('subcontractor.work',
                                        'invoice_line_id', 'Subcontractor Work'),
        'subcontractor_work_invoiced_id': fields.function(_get_work_invoiced,
                            fnct_inv=_set_work_invoiced,
                            string='Invoiced Work',
                            type='many2one',
                            relation='subcontractor.work'),
        'supplier_work_invoiced_id': fields.function(_get_work_invoiced,
                            fnct_inv=_set_work_invoiced,
                            string='Invoiced Work',
                            type='many2one',
                            relation='subcontractor.work'),
        'invalid_work_amount': fields.function(_is_work_amount_invalid,
                            string='Work Amount Invalid',
                            type='boolean'),
        'no_subcontractor_work': fields.boolean('No Subcontractor work',
            help=('This analytic account is incompatible with the workitem'
                'If you tick this box the workitem will'
                'be invisible on the invoice')
            ), 
    }

    def on_analytic_account_change(self, cr, uid, ids, account_analytic_id, context=None): 
        analytic_obj = self.pool['account.analytic.account']
        no_subcontractor_work = False
        if account_analytic_id:
            account = analytic_obj.browse(cr, uid, account_analytic_id, context=context)
            no_subcontractor_work = account.no_subcontractor_work
        return {'value': {'no_subcontractor_work': no_subcontractor_work}}
        
        
class account_invoice(orm.Model):
    _inherit = "account.invoice"

    def _get_to_pay(self, cr, uid, ids, field_name, args, context=None):
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            if invoice.state == 'paid':
                result[invoice.id] = False
            else:
                result[invoice.id] = all([line.supplier_work_invoiced_id.state == 'paid' for line in invoice.invoice_line])
        return result

    def _is_work_amount_valid(self, cr, uid, ids, field_name, args, context=None):
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            result[invoice.id] = any([line.invalid_work_amount for line in invoice.invoice_line])
        return result


    _columns = {
        'to_pay': fields.function(_get_to_pay,
                            type='boolean',
                            string='To Paid'),
        'invalid_work_amount': fields.function(_is_work_amount_valid,
                            string='Work Amount Invalid',
                            type='boolean'),
    }


    def _prepare_intercompany_line(self, cr, uid, line, *args, **kwargs):
        res = super(account_invoice, self)._prepare_intercompany_line(cr, uid,
                                                    line, *args, **kwargs)
        res['supplier_work_invoiced_id'] = line.subcontractor_work_invoiced_id.id
        return res

class account_analytic_account(orm.Model):
    _inherit = 'account.analytic.account'
    
    _columns = {
        'no_subcontractor_work': fields.boolean('No Subcontractor work',
            help=('This analytic account is incompatible with the '
                'workitem. If you tick this box the workitem '
                'will be invisible on the invoice')
            ), 
    }

