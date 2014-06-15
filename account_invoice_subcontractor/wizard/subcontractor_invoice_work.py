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

from openerp.osv import osv, orm, fields
from openerp.tools.translate import _


class subcontractor_invoice_work(orm.TransientModel):
    _name = "subcontractor.invoice.work"
    _description = "subcontractor invoice work"


    _columns = {
        'product_id': fields.many2one('product.product', 'Product', domain=[('sale_ok', '=', True)]),
    }

    #TODO FIXME
    _defaults = {
        'product_id': 5,
    }

    def _check(self, cr, uid, works, context=None):
        partner_id = works[0].customer_id.id
        for work in works:
            if partner_id != work.customer_id.id:
                raise osv.except_osv(_('User Error'),
                        _('All the work should believe to the same supplier'))
            elif work.subcontractor_invoice_line_id:
                raise osv.except_osv(_('User Error'),
                        _('This work have been already invoiced!'))
            elif not work.state in ('open', 'paid'):
                raise osv.except_osv(_('User Error'),
                        _('Only works with the state "open" or "paid" can be invoiced'))


    def _prepare_invoice(self, cr, uid, works, wizard, context=None):
        journal_obj = self.pool['account.journal']
        inv_obj = self.pool['account.invoice']
        onchange_vals = inv_obj.onchange_partner_id(cr, uid, False, 'out_invoice',
                                                 works[0].customer_id.id)
        invoice_vals = onchange_vals['value']
        journal_ids = journal_obj.search(cr, uid, [('company_id','=', works[0].subcontractor_company_id.id),
                                                   ('type', '=', 'sale')],
                                         context=context)
        invoice_vals.update({
                        'type': 'out_invoice',
                        'partner_id': works[0].customer_id.id,
                        'journal_id': journal_ids and journal_ids[0] or False,
                        'invoice_line': [],
                        'currency_id': works[0].subcontractor_company_id.currency_id.id,
        })
        return invoice_vals

    def _prepare_invoice_line(self, cr, uid, invoice_vals, work, wizard, context=None):
        invoice_line_obj = self.pool['account.invoice.line']
        onchange_vals = invoice_line_obj.product_id_change(cr, uid, False,
                               wizard.product_id.id,
                               False,
                               qty=work.quantity,
                               name=work.name,
                               type='out_invoice',
                               partner_id=invoice_vals.get('partner_id'),
                               fposition_id=invoice_vals.get('fiscal_position'),
                               price_unit=work.cost_price_unit,
                               currency_id=invoice_vals.get('currency_id'),
                               context=context)
        line_vals = onchange_vals['value']
        work_read = work.read()[0]
        line_vals.update({
                'price_unit': work.cost_price_unit,
                'quantity': work.quantity,
                'uos_id': work.uos_id.id,
                'product_id': wizard.product_id.id,
                'invoice_line_tax_id': [(6, 0, onchange_vals['value']['invoice_line_tax_id'])],
                'subcontractor_work_invoiced_id': work.id,
                'name': "Client final : %s (%s)\n%s"%(work.end_customer_id.name, work_read['invoice_id'][1], work.name),
                'no_subcontractor_work': True,
            })
        return line_vals



    def generate_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        invoice_obj = self.pool['account.invoice']
        work_obj = self.pool['subcontractor.work']
        mod_obj = self.pool.get('ir.model.data')
        wizard = self.browse(cr, uid, ids[0], context=context) 
        work_ids = context.get('active_ids')
        works = work_obj.browse(cr, uid, work_ids, context=context)
        self._check(cr, uid, works, context=context)
        invoice_vals = self._prepare_invoice(cr, uid, works, wizard, context=context)
        for work in works:
            line_vals = self._prepare_invoice_line(cr, uid, invoice_vals, work, wizard, context=context)
            invoice_vals['invoice_line'].append((0, 0, line_vals))
        
        inv_id = invoice_obj.create(cr, uid, invoice_vals, context=context)
        invoice_obj.button_reset_taxes(cr, uid, [inv_id], context)
        res = mod_obj.get_object_reference(cr, uid, 'account', 'invoice_form')
        res_id = res and res[1] or False,

        return {
            'name': _('Customer Invoices'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': 'account.invoice',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': inv_id,
        }
