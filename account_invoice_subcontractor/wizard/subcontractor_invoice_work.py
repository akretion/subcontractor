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

    @api.multi
    def generate_invoice(self):
        work_obj = self.env['subcontractor.work']
        work_ids = self._context.get('active_ids')
        works = work_obj.browse(work_ids)
        works.check()
        invoices = works.invoice_from_work()
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
