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
from openerp.tools.translate import _
from openerp.exceptions import Warning as UserError


class SubcontractorInvoiceWork(models.TransientModel):
    _name = 'subcontractor.invoice.work'
    _description = 'subcontractor invoice work'

    product_id = fields.Many2one('product.product',
                                 string='Product',
                                 domain=[('sale_ok', '=', True)],
                                 default=5)

    @api.model
    def _check(self, works):
        partner_id = works[0].customer_id.id
        for work in works:
            if partner_id != work.customer_id.id:
                raise UserError(
                    _('All the work should believe to the same supplier'))
            elif work.subcontractor_invoice_line_id:
                raise UserError(
                    _('This work have been already invoiced!'))
            elif work.state not in ('open', 'paid'):
                raise UserError(
                    _("Only works with the state 'open' "
                      " or 'paid' can be invoiced"))

    @api.model
    def _prepare_invoice(self, works, wizard):
        journal_obj = self.pool['account.journal']
        inv_obj = self.pool['account.invoice']
        onchange_vals = inv_obj.onchange_partner_id(False,
                                                    'out_invoice',
                                                    works[0].customer_id.id)
        invoice_vals = onchange_vals['value']
        journal_ids = journal_obj.search([
            ('company_id', '=', works[0].subcontractor_company_id.id),
            ('type', '=', 'sale')])
        invoice_vals.update({
            'type': 'out_invoice',
            'partner_id': works[0].customer_id.id,
            'journal_id': journal_ids and journal_ids[0] or False,
            'invoice_line': [],
            'currency_id': works[0].subcontractor_company_id.currency_id.id,
        })
        return invoice_vals

    @api.model
    def _prepare_invoice_line(self, invoice_vals, work, wizard):
        invoice_line_obj = self.pool['account.invoice.line']
        onchange_vals = invoice_line_obj.product_id_change(
            False,
            wizard.product_id.id,
            False,
            qty=work.quantity,
            name=work.name,
            type='out_invoice',
            partner_id=invoice_vals.get('partner_id'),
            fposition_id=invoice_vals.get('fiscal_position'),
            price_unit=work.cost_price_unit,
            currency_id=invoice_vals.get('currency_id'),
        )
        line_vals = onchange_vals['value']
        work_read = work.read()[0]
        line_vals.update({
            'price_unit': work.cost_price_unit,
            'quantity': work.quantity,
            'uos_id': work.uos_id.id,
            'product_id': wizard.product_id.id,
            'invoice_line_tax_id': [
                (6, 0, onchange_vals['value']['invoice_line_tax_id'])],
            'subcontractor_work_invoiced_id': work.id,
            'name': "Client final : %s (%s)\n%s" % (
                work.end_customer_id.name,
                work_read['invoice_id'][1],
                work.name),
            'no_subcontractor_work': True,
        })
        return line_vals

    @api.model
    def generate_invoice(self):
        if self._context is None:
            self._context = {}
        invoice_obj = self.pool['account.invoice']
        work_obj = self.pool['subcontractor.work']
        mod_obj = self.pool['ir.model.data']
        wizard = self.browse(self.ids[0])
        work_ids = self._context.get('active_ids')
        works = work_obj.browse(work_ids)
        self._check(works)
        invoice_vals = self._prepare_invoice(works, wizard)
        for work in works:
            line_vals = self._prepare_invoice_line(invoice_vals, work, wizard)
            invoice_vals['invoice_line'].append((0, 0, line_vals))

        inv_id = invoice_obj.create(invoice_vals)
        invoice_obj.button_reset_taxes([inv_id])
        res = mod_obj.get_object_reference('account', 'invoice_form')
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
