# © 2015 Akretion
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models
from odoo.tools.translate import _


class SubcontractorInvoiceWork(models.TransientModel):
    _name = "subcontractor.invoice.work"
    _description = "subcontractor invoice work"

    def generate_invoice(self):
        work_obj = self.env["subcontractor.work"]
        work_ids = self._context.get("active_ids")
        works = work_obj.browse(work_ids)
        works.check()
        invoices = works.invoice_from_work()
        return {
            "name": _("Customer Invoices"),
            # 'view_type': 'form',
            "view_mode": "tree,form",
            "res_model": "account.invoice",
#            "context": "{'type':'out_invoice'}",
            "type": "ir.actions.act_window",
            "nodestroy": True,
            "target": "current",
            "domain": "[('id','in', %s)]" % invoices.ids,
        }
