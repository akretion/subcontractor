# Copyright 2022 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.contract.tests.test_contract import TestContractBase


class TestContractInvoiceProject(TestContractBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contract.date_end = "2018-12-31"
        cls.acct_line.project_id = cls.env.ref("project.project_project_1").id

    def test_invoice_project(self):
        invoice = self.contract.recurring_create_invoice()
        self.assertEqual(
            invoice.invoice_line_ids.project_id,
            self.env.ref("project.project_project_1"),
        )
        self.assertTrue(invoice.invoice_line_ids.end_date)
