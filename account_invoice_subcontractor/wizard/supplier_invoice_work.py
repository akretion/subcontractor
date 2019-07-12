# coding: utf-8
# © 2015 Akretion
#   @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models
from odoo.tools.translate import _


class SupplierInvoiceWork(models.TransientModel):
    _name = "supplier.invoice.work"
    _description = "supplier invoice work"

    @api.multi
    def generate_invoice(self):
        work_obj = self.env["subcontractor.work"]
        work_ids = self._context.get("active_ids")
        works = work_obj.browse(work_ids)
        works.check(work_type="external")
        invoice = works.supplier_invoice_from_work()
        return {
            "name": _("Supplier Invoice"),
            # 'view_type': 'form',
            "view_mode": "form,tree",
            "res_model": "account.invoice",
            "res_id": invoice.id,
            "context": "{'type':'in_invoice'}",
            "type": "ir.actions.act_window",
            "nodestroy": True,
            "target": "current",
            "domain": "[('type','=', 'in_invoice')]",
        }
