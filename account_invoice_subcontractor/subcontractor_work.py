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
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp

INVOICE_STATE = [
    ('draft', 'Draft'),
    ('proforma', 'Pro-forma'),
    ('proforma2', 'Pro-forma'),
    ('open', 'Open'),
    ('paid', 'Paid'),
    ('cancel', 'Cancelled'),
]


class SubcontractorWork(models.Model):
    _name = "subcontractor.work"
    _description = "subcontractor work"

    @api.multi
    @api.depends('invoice_line_id',
                 'invoice_line_id.invoice_id.state',
                 'supplier_invoice_line_id',
                 'supplier_invoice_line_id.invoice_id.state'
                 )
    def _get_state(self):
        for work in self.sudo().browse():
            if work.invoice_line_id:
                work.state = work.invoice_line_id.invoice_id.state
            if work.supplier_invoice_line_id:
                work.subcontractor_state = (work.supplier_invoice_line_id.
                                            invoice_id.state)

    @api.onchange('employee_id')
    def employee_id_onchange(self):
        if self.employee_id:
            self.subcontractor_type = self.employee_id.subcontractor_type

    @api.multi
    def _get_work_from_sup_invoice(self):
        work_obj = self.pool['subcontractor.work']
        work_ids = work_obj.search(
            [('supplier_invoice_line_id.invoice_id', 'in', self.ids)])
        return work_ids

    @api.multi
    def _get_work_from_invoice(self):
        work_obj = self.pool['subcontractor.work']
        work_ids = work_obj.search(
            [('invoice_line_id.invoice_id', 'in', self.ids)])
        return work_ids

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
    sale_price_unit = fields.Float(
        digits=dp.get_precision('Account'))
    cost_price_unit = fields.Float(
        compute='_compute_price',
        digits=dp.get_precision('Account'),
        store=True)
    cost_price = fields.Float(
        compute='_compute_price',
        digits=dp.get_precision('Account'),
        store=True)
    sale_price = fields.Float(
        compute='_compute_price',
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
        store=True)
    subcontractor_type = fields.Selection(selection=_get_subcontractor_type)
    state = fields.Selection(
        compute='_get_state',
        selection=INVOICE_STATE,
        store=True,
        default='draft')
    uos_id = fields.Many2one(
        'product.uom',
        string='Product UOS')

    @api.multi
    @api.depends('sale_price_unit', 'quantity')
    def _compute_price(self):
        for work in self:
            rate = 1
            if work.invoice_line_id.product_id.no_commission:
                rate -= work.employee_id.\
                    subcontractor_company_id.commission_rate/100.
            work.cost_price_unit = work.sale_price_unit * rate
            work.cost_price = work.quantity * work.cost_price_unit
            work.sale_price = work.quantity * work.sale_price_unit
