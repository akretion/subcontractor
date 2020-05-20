# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestInvoicing(TransactionCase):
    def mref(self, xml):
        return self.env.ref("project_invoicing_subcontractor.%s" % xml)

    def setUp(self):
        super(TestInvoicing, self).setUp()
        self.line_1 = self.mref("account_analytic_line_1")
        self.line_2 = self.mref("account_analytic_line_2")
        self.line_3 = self.mref("account_analytic_line_3")
        self.line_4 = self.mref("account_analytic_line_4")
        self.line_5 = self.mref("account_analytic_line_5")
        self.partner = self.env.ref("base.res_partner_4")
        self.invoice = self.env["account.invoice"].create(
            {"partner_id": self.partner.id}
        )
        self.product = self.mref("product_product_1")
        self.day_uom = self.env.ref("product.product_uom_day")
        self.hour_uom = self.env.ref("product.product_uom_hour")
        self.project = self.mref("project_project_1")

    def _create_invoice(self):
        line_ids = [self.line_3.id, self.line_4.id, self.line_5.id]
        wizard = (
            self.env["subcontractor.timesheet.invoice"]
            .with_context(active_ids=line_ids)
            .create({"partner_id": self.partner.id, "invoice_id": self.invoice.id})
        )
        wizard.action_invoice()
        return wizard.invoice_id

    def test_invoicing_in_days(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.amount_untaxed, 1125)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line_1 = invoice.invoice_line_ids[0]
        self.assertEqual(line_1.quantity, 1.5)
        self.assertEqual(line_1.price_unit, 500)
        self.assertEqual(line_1.uom_id, self.day_uom)
        self.assertEqual(line_1.product_id, self.product)

    def test_invoicing_in_hours(self):
        self.project.uom_id = self.hour_uom
        invoice = self._create_invoice()
        self.assertEqual(invoice.amount_untaxed, 1125)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line_1 = invoice.invoice_line_ids[0]
        self.assertEqual(line_1.quantity, 12)
        self.assertEqual(line_1.price_unit, 62.5)
        self.assertEqual(line_1.uom_id, self.hour_uom)
        self.assertEqual(line_1.product_id, self.product)

    def test_invoicing_with_discount(self):
        self.line_3.discount = 50
        self.project.uom_id = self.hour_uom
        invoice = self._create_invoice()
        self.assertEqual(invoice.amount_untaxed, 875)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line_1 = invoice.invoice_line_ids[0]
        self.assertEqual(line_1.quantity, 8)
        self.assertEqual(line_1.price_unit, 62.5)
        self.assertEqual(line_1.uom_id, self.hour_uom)
        self.assertEqual(line_1.product_id, self.product)

    def _test_invoiceable(self, invoicing, finished, expected):
        task = self.line_1.task_id
        if finished:
            task.stage_id = task.project_id.invoicing_stage_id
        task.invoicing = invoicing
        self.assertEqual(self.line_1.invoiceable, expected)

    def test_invoiceable_case_not_finished(self):
        self._test_invoiceable("finished", finished=False, expected=False)

    def test_invoiceable_case_finished(self):
        self._test_invoiceable("finished", finished=True, expected=True)

    def test_invoiceable_case_none_invoiceable(self):
        self._test_invoiceable("none", finished=True, expected=False)

    def test_invoiceable_case_progressive_invoiceable(self):
        self._test_invoiceable("progressive", finished=False, expected=True)

    def test_invoiceable_case_full_discount(self):
        self.line_1.discount = 100
        self._test_invoiceable("finished", finished=True, expected=False)

    def test_invoiceable_hours(self):
        self.assertEqual(self.line_1.task_id.invoiceable_hours, 2)
        self.line_1.discount = 50
        self.assertEqual(self.line_1.task_id.invoiceable_hours, 1)

    def test_change_task_project(self):
        project = self.env.ref("project.project_project_1")
        self.line_1.task_id.project_id = project
        self.assertEqual(self.line_1.project_id, project)
        self.assertEqual(self.line_1.account_id, project.analytic_account_id)

    def test_remove_task_project(self):
        with self.assertRaises(UserError):
            self.line_1.task_id.project_id = False
