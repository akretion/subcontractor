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

    @api.multi
    def check(self):
        partner_id = self[0].customer_id.id
        for work in self:
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

    @api.multi
    def _prepare_invoice(self):
        self.ensure_one()
        journal_obj = self.env['account.journal']
        inv_obj = self.env['account.invoice']
        company = self.subcontractor_company_id
        journal = journal_obj.search([
            ('company_id', '=', company.id),
            ('type', '=', 'sale')],
            limit=1)
        if not journal:
            raise UserError(
                    _('Please define sale journal for this company: "%s" (id:%d).')
                % (company.name, company.id))
        onchange_vals = inv_obj.onchange_partner_id(
            'out_invoice',  self.customer_id.id)
        invoice_vals = onchange_vals['value']
        subcontractor_company = self.company_id
        user = self.env['res.users'].search([
            ('company_id', '=', company.id)], limit=1)
        invoice_vals.update({
            'date_invoice': date.today(),
            'type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'journal_id': journal.id,
            'invoice_line': [(6, 0, [])],
            'currency_id': company.currency_id.id,
            'user_id': user.id,
        })
        return invoice_vals

    @api.model
    def _prepare_invoice_line(self, invoice):
        self.ensure_one()
        invoice_line_obj = self.env['account.invoice.line']
        line_data = invoice_line_obj.product_id_change(
            product=self.sudo().invoice_line_id.product_id.id,
            uom_id=False,
            qty=self.quantity,
            name=self.name,
            type='out_invoice',
            partner_id=invoice.partner_id and invoice.partner_id.id or False,
            fposition_id=invoice.fiscal_position and invoice.fiscal_position.id or False,
            price_unit=self.cost_price_unit,
            currency_id=invoice.currency_id and invoice.currency_id.id or False,
            company_id=invoice.company_id and invoice.company_id.id or False)
        line_vals = line_data['value']
        line_vals.update({
            'uos_id': self.uos_id.id,
            'price_unit': self.cost_price_unit,
            'invoice_id': invoice.id,
            'discount': self.sudo().invoice_line_id.discount,
            'quantity': self.quantity,
            'product_id': self.sudo().invoice_line_id.product_id.id,
            'invoice_line_tax_id': [
                (6, 0, line_data['value']['invoice_line_tax_id'])],
            'subcontractor_work_invoiced_id': self.id,
            'name': "Client final %s :%s" % (
                self.end_customer_id.name,
                self.name),
        })
        return line_vals

    @api.multi
    def invoice_from_work(self):
        invoice_line_obj = self.env['account.invoice.line']
        invoice_obj = self.env['account.invoice']
        invoices = self.env['account.invoice']
        current_employee_id = None
        current_invoice_id = None
        for work in self:
            if (current_employee_id != work.employee_id
                    or current_invoice_id != work.invoice_id):
                invoice_vals = work._prepare_invoice()
                invoice = invoice_obj.create(invoice_vals)
                current_employee_id = work.employee_id
                current_invoice_id = work.invoice_id
                invoices |= invoice
            inv_line_data = (
                work._prepare_invoice_line(invoice))
            # Need sudo because odoo prefetch de work.invoice_id
            # and try to read fields on it and that makes access rules fail
            inv_line = invoice_line_obj.sudo().create(inv_line_data)
            invoice.sudo().write({'invoice_line': [(6, 0, [inv_line.id])]})
        invoices.button_reset_taxes()
        return invoices

    @api.multi
    def _scheduler_action_subcontractor_invoice_create(self):
        date_filter = date.today() - timedelta(days=7)
        subcontractors = self.env['hr.employee'].search(
            [('subcontractor_type', '=', 'internal'),
             ('subcontractor_company_id', '!=', False)])
        for subcontractor in subcontractors:
            user = subcontractor.subcontractor_company_id.intercompany_user_id
            if not user or user.id !=55:
                continue
            if user.company_id != subcontractor.subcontractor_company_id:
                user.company_id = subcontractor.subcontractor_company_id
            subcontractor_works = self.sudo(user).search([
#                    ('invoice_id.date_invoice', '<=', date_filter),
                    ('subcontractor_invoice_line_id', '=', False),
                    ('subcontractor_type', '=', 'internal'),
                    ('state', 'in', ['open', 'paid']),
                    ('employee_id', '=', subcontractor.id)
                ], order='employee_id, invoice_id')
            invoices = subcontractor_works.invoice_from_work()
            invoices.signal_workflow('invoice_open')
        return True
