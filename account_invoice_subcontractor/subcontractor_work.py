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
from openerp import models, fields, api, _
from datetime import timedelta, date
from openerp.exceptions import Warning as UserError
import openerp.addons.decimal_precision as dp


INVOICE_STATE = [
    ('draft', 'Draft'),
    ('open', 'Open'),
    ('paid', 'Paid'),
    ('cancel', 'Cancelled'),
]


class SubcontractorWork(models.Model):
    _name = "subcontractor.work"
    _description = "subcontractor work"

    @api.model
    def _get_subcontractor_type(self):
        return self.env['hr.employee']._get_subcontractor_type()

    name = fields.Text(
        related='invoice_line_id.name',
        readonly=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True)
    invoice_line_id = fields.Many2one(
        'account.invoice.line',
        string='Invoice Line',
        required=True,
        ondelete="cascade")
    invoice_id = fields.Many2one(
        'account.invoice',
        related='invoice_line_id.invoice_id',
        string='Invoice',
        store=True)
    supplier_invoice_line_id = fields.Many2one(
        'account.invoice.line',
        string='Supplier Invoice Line')
    supplier_invoice_id = fields.Many2one(
        'account.invoice',
        related='supplier_invoice_line_id.invoice_id',
        string='Supplier Invoice')
    quantity = fields.Float(
        digits=dp.get_precision('Product UoS'))
    sale_price_unit = fields.Float(digits=dp.get_precision('Account'))
    cost_price_unit = fields.Float(digits=dp.get_precision('Account'))
    cost_price = fields.Float(
        compute='_compute_total_price',
        digits=dp.get_precision('Account'),
        store=True)
    sale_price = fields.Float(
        compute='_compute_total_price',
        digits=dp.get_precision('Account'),
        store=True)
    company_id = fields.Many2one(
        'res.company',
        related='invoice_line_id.company_id',
        string='Company',
        readonly=True)
    customer_id = fields.Many2one(
        'res.partner',
        related='company_id.partner_id',
        readonly=True,
        string='Customer')
    end_customer_id = fields.Many2one(
        'res.partner',
        related='invoice_id.partner_id',
        readonly=True,
        string='Customer(end)')
    subcontractor_invoice_line_id = fields.Many2one(
        'account.invoice.line',
        string='Subcontractor Invoice Line')
    subcontractor_company_id = fields.Many2one(
        'res.company',
        related='employee_id.subcontractor_company_id',
        readonly=True,
        store=True,
        string='Subcontractor Company')
    subcontractor_state = fields.Selection(
        compute='_get_state',
        selection=INVOICE_STATE,
        store=True,
        compute_sudo=True)
    subcontractor_type = fields.Selection(
        string='Subcontractor Type',
        selection='_get_subcontractor_type')
    state = fields.Selection(
        compute='_get_state',
        selection=INVOICE_STATE,
        store=True,
        default='draft',
        compute_sudo=True)
    uos_id = fields.Many2one(
        'product.uom',
        related='invoice_line_id.uos_id',
        readonly=True,
        string='Product UOS')

    @api.onchange('sale_price_unit', 'employee_id')
    def _compute_price(self):
        for work in self:
            rate = 1
            if not work.invoice_line_id.product_id.no_commission:
                rate -= work.employee_id.\
                    subcontractor_company_id.commission_rate/100.
            work.cost_price_unit = work.sale_price_unit * rate

    @api.onchange('employee_id')
    def employee_id_onchange(self):
        self.ensure_one()
        if self.employee_id:
            self.subcontractor_type = self.employee_id.subcontractor_type
            line = self.invoice_line_id
            #TODO find a good way to get the right qty
            self.quantity = line.quantity
            self.sale_price_unit = line.price_unit * (1 - line.discount / 100.)

    @api.multi
    @api.depends('sale_price_unit', 'quantity', 'cost_price_unit')
    def _compute_total_price(self):
        for work in self:
            work.cost_price = work.quantity * work.cost_price_unit
            work.sale_price = work.quantity * work.sale_price_unit

    @api.multi
    @api.depends('invoice_line_id',
                 'invoice_line_id.invoice_id.state',
                 'supplier_invoice_line_id',
                 'supplier_invoice_line_id.invoice_id.state'
                 )
    def _get_state(self):
        for work in self:
            if work.invoice_line_id:
                work.state = work.invoice_line_id.invoice_id.state
            if work.supplier_invoice_line_id:
                work.subcontractor_state = (work.supplier_invoice_line_id.
                                            invoice_id.state)

    @api.model
    def _prepare_subcontractor_invoice_data(self, work):
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', work.subcontractor_company_id.id)
        ], limit=1)
        if not journal:
            company = work.subcontractor_company_id
            raise UserError(
                _('Please define sale journal for this company: "%s" (id:%d).')
                % (company.name, company.id))
        subcontractor_company = work.subcontractor_company_id
        users = self.pool['res.users'].search([
            ('company_id', '=', subcontractor_company.id)])
        return {
            'origin': self.company_id.name + _(' Invoice: ') + str(
                work.invoice_id.number),
            'type': 'out_invoice',
            'date_invoice': date.today(),
            'account_id': (self.company_id.partner_id.
                           property_account_receivable.id),
            'partner_id': self.company_id.partner_id.id,
            'journal_id': journal.id,
            'invoice_line': [(6, 0, [])],
            'currency_id': (subcontractor_company.currency_id
                            and subcontractor_company.currency_id.id),
            'fiscal_position': (self.company_id.partner_id.
                                property_account_position),
            'company_id': subcontractor_company.id,
            'partner_bank_id': subcontractor_company.bank_ids[0].id,
            'user_id': users[0].id
        }

    @api.model
    def _prepare_subcontractor_invoice_line_data(self, invoice_vals, work):
        invoice_line_obj = self.pool['account.invoice.line']
        line_data = invoice_line_obj.sudo().product_id_change(
            product=work.invoice_line_id.product_id.id,
            uom_id=False,
            qty=work.quantity,
            name=work.name,
            type='out_invoice',
            partner_id=invoice_vals.get('partner_id'),
            fposition_id=invoice_vals.get('fiscal_position'),
            price_unit=work.cost_price_unit,
            currency_id=invoice_vals.get('currency_id'),
            company_id=invoice_vals.get('company_id'))
        line_data.update({
            'uos_id': work.uos_id.id,
            'invoicing_type': work.invoice_line_id.invoicing_type,
            'discount': work.invoice_line_id.discount,
            'invoice_line_tax_id': [
                (6, 0, line_data['value']['invoice_line_tax_id'])],
            'name': "Client final %s: %s" % (work.end_customer_id.name,
                                             work.name),
            'subcontractor_work_invoiced_id': work.id,
        })
        return line_data

    @api.multi
    def _scheduler_action_subcontractor_invoice_create(self):
        invoice_line_obj = self.pool['account.invoice.line']
        invoice_obj = self.pool['account.invoice']
        date_filter = date.today() - timedelta(days=7)
        subcontractor_works = self.search([
            ('invoice_id.date_invoice', '<=', date_filter),
            ('subcontractor_invoice_line_id', '=', False),
            ('subcontractor_type', '=', 'internal'),
            ('state', 'in', ['open', 'paid'])
        ], order=['employee_id', 'invoice_id'])
        current_employee_id = None
        current_invoice_id = None
        for work in subcontractor_works:
            if (current_employee_id != work.employee_id
                    or current_invoice_id != work.invoice_id):
                # create invoice, as the internal subcontrator
                invoice_vals = self.sudo()._prepare_subcontractor_invoice_data(
                    work)
                invoice = invoice_obj.sudo().create(invoice_vals)
                current_employee_id = work.employee_id
                current_invoice_id = work.invoice_id
            # create invoice line, as the internal subcontractor
            inv_line_data = (
                self.sudo()._prepare_subcontractor_invoice_line_data(
                    invoice_vals, work))
            inv_line_id = invoice_line_obj.sudo().create(inv_line_data)
            # update invoice with invoice line created
            invoice.write({'invoice_line': [(6, 0, [inv_line_id])]})
        return True
