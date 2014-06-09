# -*- coding: utf-8 -*-
###############################################################################
#
#   Module for OpenERP 
#   Copyright (C) 2013 Akretion (http://www.akretion.com).
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

from openerp.osv import fields, orm

class project_task(orm.Model):
    _inherit = 'project.task'
    
    def _prepare_subcontractor_vals(self, cr, uid, task, inv_line_vals, context=None):
        uom_id, qty = self._get_qty2invoice(cr, uid, task, context=context)
        return {
            #TODO FIXME do not take the first employee
            'employee_id': task.user_id.employee_ids[0].id,
            'quantity': qty,
            'uos_id': uom_id,
            'sale_price_unit': inv_line_vals['price_unit'],
        }

    def _prepare_invoice_line_vals(self, cr, uid, task, invoice_vals, context=None):
        inv_line_vals = super(project_task, self).\
            _prepare_invoice_line_vals(cr, uid, task, invoice_vals, context=context)
        subcontractor_vals = self._prepare_subcontractor_vals(cr, uid, task,
            inv_line_vals, context=context)
        inv_line_vals['subcontractor_work_ids'] = [(0, 0, subcontractor_vals)]
        return inv_line_vals
