# -*- coding: utf-8 -*-
# © 2013-2017 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)


from odoo import api, fields, models


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    task_id = fields.Many2one('project.task')
    task_stage_id = fields.Many2one(
        'project.task.type',
        related='task_id.stage_id',
        store=True)

    def open_task(self):
        self.ensure_one()
        action = self.env.ref('project.action_view_task').read()[0]
        action.update({
            'res_id': self.task_id.id,
            'views': [x for x in action['views'] if x[1] == 'form'],
            })
        return action

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def action_view_subcontractor(self):
        self.ensure_one()
        action = self.env.ref(
            'account_invoice_subcontractor.action_subcontractor_work').read()[0]
        action['context'] = {
            'search_default_invoice_id': self.id,
            'search_default_subcontractor': 1,
            }
        return action

    def action_view_analytic_line(self):
        self.ensure_one()
        action = self.env.ref(
            'hr_timesheet.act_hr_timesheet_line').read()[0]
        action['context'] = {
            'search_default_invoice_id': self.id,
            'search_default_users': 1,
            'search_default_tasks': 1,
            }
        return action
