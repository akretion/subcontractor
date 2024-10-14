# Copyright 2019-2020 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractLine(models.Model):
    _inherit = "contract.line"

    project_id = fields.Many2one("project.project")

    def _prepare_invoice_line(self):
        vals = super()._prepare_invoice_line()
        vals["project_id"] = self.project_id.id
        return vals
