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
import openerp.addons.decimal_precision as dp
from openerp import SUPERUSER_ID

INVOICE_STATE = [
    ('draft','Draft'),
    ('proforma','Pro-forma'),
    ('proforma2','Pro-forma'),
    ('open','Open'),
    ('paid','Paid'),
    ('cancel','Cancelled'),
]

class subcontractor_work(orm.Model):
    _name = "subcontractor.work"
    _description = "subcontractor work"


    def _get_state(self, cr, uid, ids, fields, args, context=None):
        result = {}
        for work in self.browse(cr, SUPERUSER_ID, ids, context=context):
            result[work.id] = {'state': None, 'subcontractor_state': None}
            if work.invoice_line_id:
                result[work.id]['state'] = work.invoice_line_id.invoice_id.state
            if work.supplier_invoice_line_id:
                result[work.id]['subcontractor_state'] = work.supplier_invoice_line_id.invoice_id.state
        return result

    _columns = {
        'name': fields.related('invoice_line_id', 'name',
                                    type='text',
                                    readonly=True,
                                    string='Name'),

        'employee_id':fields.many2one('hr.employee', 'Employee',
                                    required=True),

        'invoice_line_id':fields.many2one('account.invoice.line', 'Invoice Line',
                                    required=True),

        'supplier_invoice_line_id':fields.many2one('account.invoice.line',
                                            'Supplier Invoice Line'),

        'quantity': fields.float('Quantity', 
                                    digits_compute= dp.get_precision('Product UoS')),

        'sale_price_unit': fields.float('Sale Unit Price',
                                    digits_compute= dp.get_precision('Account')),

        'cost_price_unit': fields.float('Cost Unit Price', readonly=True,
                                    digits_compute= dp.get_precision('Account')),

        'company_id':fields.related('invoice_line_id', 'company_id',
                                    type='many2one',
                                    relation='res.company',
                                    string='Company',
                                    readonly=True),

        'customer_id': fields.related('company_id', 'partner_id',
                                    type='many2one',
                                    relation='res.partner',
                                    readonly=True,
                                    string='Customer'),

        'subcontractor_invoice_line_id':fields.many2one('account.invoice.line',
                                            'Subcontractor Invoice Line'),

        'subcontract_company_id': fields.related('employee_id', 'subcontractor_company_id',
                                    type='many2one',
                                    relation='res.company',
                                    readonly=True,
                                    string='Subcontractor Company'),

        #TODO add store and invalidation function
        'subcontractor_state': fields.function(_get_state,
                                    string='Subcontractor State',
                                    type='selection',
                                    selection = INVOICE_STATE,
                                    multi='state'),

        'state': fields.function(_get_state,
                                    string='State',
                                    type='selection',
                                    selection = INVOICE_STATE,
                                    multi='state'),
    }

    _defaults = {
        'state': 'draft',
        'subcontractor_state': 'draft',
    }

    def _update_cost_price(self, cr, uid, vals, context=None):
        #TODO take me from some configuration (on partner or company)
        if vals.get('sale_price_unit'):
            vals['cost_price_unit'] = vals['sale_price_unit'] * 0.9
        return True

    def create(self, cr, uid, vals, context=None):
        self._update_cost_price(cr, uid, vals, context=context)
        return super(subcontractor_work, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        self._update_cost_price(cr, uid, vals, context=context)
        return super(subcontractor_work, self).write(cr, uid, ids, vals, context=context)
