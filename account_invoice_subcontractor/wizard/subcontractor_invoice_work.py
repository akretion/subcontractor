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

from openerp import models, api
from openerp.tools.translate import _
from openerp.exceptions import Warning as UserError
from datetime import date


class SubcontractorInvoiceWork(models.TransientModel):
    _name = 'subcontractor.invoice.work'
    _description = 'subcontractor invoice work'

    @api.model
    def _check(self, works):
        partner_id = works[0].customer_id.id
        for work in works:
            if partner_id != work.customer_id.id:
                raise UserError(
                    _('All the work should belong to the same supplier'))
            elif work.supplier_invoice_line_id:
                raise UserError(
                    _('This work has been already invoiced!'))
            elif work.state not in ('open', 'paid'):
                raise UserError(
                    _("Only works with the state 'open' "
                      " or 'paid' can be invoiced"))
            elif work.subcontractor_type != 'internal':
                raise UserError(
                    _("You can invoice on only the internal subcontractors"))

    @api.model
    def _prepare_invoice(self, work):
        journal_obj = self.env['account.journal']
        inv_obj = self.env['account.invoice']
        journal = journal_obj.sudo().search([
            ('company_id', '=', work.company_id.id),
            ('type', '=', 'sale')],
            limit=1)
        if not journal:
            raise UserError(
                    _('Please define sale journal for this company: "%s" (id:%d).')
                % (work.company_id.name, work.company_id.id))
        onchange_vals = inv_obj.onchange_partner_id('out_invoice',  work.customer_id.id)
        invoice_vals = onchange_vals['value']
        subcontractor_company = work.company_id
        user = self.env['res.users'].search([
            ('company_id', '=', subcontractor_company.id)], limit=1)
        invoice_vals.update({
            'date_invoice': date.today(),
            'type': 'out_invoice',
            'partner_id': work.customer_id.id,
            'journal_id': journal.id,
            'invoice_line': [(6, 0, [])],
            'currency_id': work.company_id.currency_id.id,
            'user_id': user.id,
        })
        return invoice_vals

    @api.model
    def _prepare_invoice_line(self, work, invoice):
        invoice_line_obj = self.env['account.invoice.line']
        line_data = invoice_line_obj.product_id_change(
            product=work.invoice_line_id.product_id.id,
            uom_id=False,
            qty=work.quantity,
            name=work.name,
            type='out_invoice',
            partner_id=invoice.partner_id and invoice.partner_id.id or False,
            fposition_id=invoice.fiscal_position and invoice.fiscal_position.id or False,
            price_unit=work.cost_price_unit,
            currency_id=invoice.currency_id and invoice.currency_id.id or False,
            company_id=invoice.company_id and invoice.company_id.id or False)
        line_vals = line_data['value']
        line_vals.update({
            'uos_id': work.uos_id.id,
            'price_unit': work.cost_price_unit,
            'invoice_id': invoice.id,
            'discount': work.invoice_line_id.discount,
            'quantity': work.quantity,
            'product_id': work.invoice_line_id.product_id.id,
            'invoice_line_tax_id': [
                (6, 0, line_data['value']['invoice_line_tax_id'])],
            'subcontractor_work_invoiced_id': work.id,
            'name': "Client final %s :%s" % (
                work.end_customer_id.name,
                work.name),
        })
        return line_vals

    @api.multi
    def generate_invoice(self):
        invoice_obj = self.env['account.invoice']
        invoice_line_obj = self.env['account.invoice.line']
        # browse work with sudo to be able to read the invoice_line
        work_obj = self.env['subcontractor.work'].sudo()
        work_ids = self._context.get('active_ids')
        works = work_obj.browse(work_ids)
        self._check(works)
        current_employee_id = None
        current_invoice_id = None
        invoices = self.env['account.invoice']
        for work in works:
            if (current_employee_id != work.employee_id
                    or current_invoice_id != work.invoice_id):
                invoice_vals = self._prepare_invoice(work)
                invoice = invoice_obj.create(invoice_vals)
                current_employee_id = work.employee_id
                current_invoice_id = work.invoice_id
                invoices |= invoice
            inv_line_data = (
                self._prepare_invoice_line(work, invoice))
            inv_line = invoice_line_obj.create(inv_line_data)
            invoice.write({'invoice_line': [(6, 0, [inv_line.id])]})
        invoices.button_reset_taxes()
        return {
            'name': _('Customer Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'domain': "[('id','in', %s)]" % invoices.ids,
        }
