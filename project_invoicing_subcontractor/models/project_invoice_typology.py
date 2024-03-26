# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models


class ProjectInvoiceTypology(models.Model):
    _name = "project.invoice.typology"
    _description = "Typology of customer invoicing from a project"

    name = fields.Char(required=True)
    usage = fields.Text()
    product_id = fields.Many2one("product.product", required=True)
    invoicing_mode = fields.Selection(
        [
            ("customer_postpaid", "Customer (postpaid)"),
            ("customer_prepaid", "Customer (prepaid)"),
            ("supplier", "Supplier"),
        ],
        compute="_compute_invoicing_mode",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    @api.depends("product_id.subcontracted", "product_id.prepaid_revenue_account_id")
    def _compute_invoicing_mode(self):
        for rec in self:
            rec = rec.with_company(rec.company_id.id)
            if rec.product_id.prepaid_revenue_account_id:
                rec.invoicing_mode = "customer_prepaid"
            elif rec.product_id.subcontracted:
                rec.invoicing_mode = "customer_postpaid"
            else:
                rec.invoicing_mode = "supplier"
