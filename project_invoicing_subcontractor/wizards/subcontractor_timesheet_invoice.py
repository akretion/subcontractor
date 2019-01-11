# -*- coding: utf-8 -*-
# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models, _


class SubcontractorTimesheetInvoice(models.TransientModel):
    _name = "subcontractor.timesheet.invoice"

    partner_id = fields.Many2one('res.partner', readonly=True)
    invoice_id = fields.Many2one('account.invoice')
    error = fields.Text(readonly=True)

    @api.onchange('error')
    def onchange_error(self):
        line_ids = self.env.context['active_ids']
        datas = self.env['account.analytic.line'].read_group(
            [('id', 'in', line_ids)],
            'partner_id',
            'partner_id',
            )
        if len(datas) > 1:
            self.error = _("You can only invoice timesheet with the same partner."
                      "Partner found %s") % [x['partner_id'] for x in datas]
        else:
            self.partner_id=datas[0]['partner_id'][0]

    def _extract_timesheet(self):
        """Return a dict with
        { <task_id> :
            {<employee_id> : <timesheet_line_ids>}
        }
        """
        res = {}
        line_obj = self.env['account.analytic.line']
        group_lines = line_obj.read_group(
            [('id', 'in', self._context['active_ids'])],
            ['task_id', 'user_id', 'unit_amount'],
            ['task_id', 'user_id'],
            lazy=False)
        for group in group_lines:
            task_id = group['task_id'][0]
            user = self.env['res.users'].browse(group['user_id'][0])
            #TODO found a better solution then getting the first employee
            employee_id = user.employee_ids[0].id
            lines = line_obj.search(group['__domain'])
            if not task_id in res:
                res[task_id] = {employee_id: lines.ids}
            else:
                res[task_id][employee_id] = lines.ids
        return res

    def _prepare_subcontractor_work(self, inv_line_id, employee_id, line_ids):
        lines = self.env['account.analytic.line'].browse(line_ids)
        vals = {
            'employee_id': employee_id,
            # TODO convert correctly to day
            'quantity': sum(lines.mapped('unit_amount'))/8.0,
            'invoice_line_id': inv_line_id,
            'timesheet_line_ids': [(6, 0, line_ids)],
        }
        record = self.env['subcontractor.work'].new(vals)
        record.employee_id_onchange()
        record._compute_price()
        vals.update({
            'sale_price_unit': record.sale_price_unit,
            'cost_price_unit': record.cost_price_unit,
            'subcontractor_type': record.subcontractor_type,
            })
        return vals

    def _prepare_invoice_line(self, task_id, data):
        line_obj = self.env['account.invoice.line']
        # HACK for POC TODO this should be configurable
        product_id = 5
        product = self.env['product.product'].browse(product_id)
        price_unit = product.lst_price
        ####
        task = self.env['project.task'].browse(task_id)
        vals = {
            'task_id': task_id,
            'invoice_id': self.invoice_id.id,
            'product_id': product_id,
            'price_unit': price_unit,
            'name': task.name,
            'subcontracted': True,
            }
        vals = line_obj.play_onchanges(vals, ['product_id'])
        return vals



    def _add_update_invoice_line(self, task_id, data):
        line_obj = self.env['account.invoice.line']
        work_obj = self.env['subcontractor.work']
        line = line_obj.search([
            ('invoice_id', '=', self.invoice_id.id),
            ('task_id', '=', task_id)])
        if not line:
           line_vals = self._prepare_invoice_line(task_id, data)
           line = line_obj.create(line_vals)
        else:
            #TODO
            raise NotImplemented
        # TODO FIX unit conversion
        qty_day = 0
        for employee_id, line_ids in data.items():
            val = self._prepare_subcontractor_work(
                line.id, employee_id, line_ids)
            qty_day += val['quantity']
            work = work_obj.create(val)
        line.quantity = qty_day

    @api.multi
    def action_invoice(self):
        self.ensure_one()
        # TODO
        # récupérer des données structuré
        # {tak_id: ('employee_id', time, timesheet_ids)}
        res = self._extract_timesheet()
        if not self.invoice_id:
            # self.invoice_id = ...
            raise NotImplemented
        for task_id, data in res.items():
            self._add_update_invoice_line(task_id, data)
        self.invoice_id.compute_taxes()
