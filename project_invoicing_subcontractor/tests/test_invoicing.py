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
        self.admin_user = self.env.ref("base.user_admin")
        self.line_1 = self.mref("account_analytic_line_1")
        self.line_2 = self.mref("account_analytic_line_2")
        self.line_3 = self.mref("account_analytic_line_3")
        self.line_4 = self.mref("account_analytic_line_4")
        self.line_5 = self.mref("account_analytic_line_5")
        self.line_6 = self.mref("account_analytic_line_6")
        self.line_7 = self.mref("account_analytic_line_7")
        self.partner = self.env.ref("base.res_partner_4")
        self.invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                "move_type": "out_invoice",
            }
        )
        self.product = self.mref("product_product_1")
        self.day_uom = self.env.ref("uom.product_uom_day")
        self.hour_uom = self.env.ref("uom.product_uom_hour")
        self.project = self.mref("project_project_1")

    def _create_invoice(self, line_ids=None):
        line_ids = line_ids or [self.line_3.id, self.line_4.id, self.line_5.id]
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
        self.assertEqual(line_1.product_uom_id, self.day_uom)
        self.assertEqual(line_1.product_id, self.product)

    def test_invoicing_in_hours(self):
        self.project.uom_id = self.hour_uom
        invoice = self._create_invoice()
        self.assertEqual(invoice.amount_untaxed, 1125)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line_1 = invoice.invoice_line_ids[0]
        self.assertEqual(line_1.quantity, 12)
        self.assertEqual(line_1.price_unit, 62.5)
        self.assertEqual(line_1.product_uom_id, self.hour_uom)
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
        self.assertEqual(line_1.product_uom_id, self.hour_uom)
        self.assertEqual(line_1.product_id, self.product)

    def test_invoicing_update_multiple_employee(self):
        line_ids = [self.line_6.id, self.line_3.id, self.line_4.id, self.line_5.id]
        invoice = self._create_invoice(line_ids=line_ids)
        line_1 = invoice.invoice_line_ids[0]
        line2 = invoice.invoice_line_ids - line_1
        self.assertEqual(line_1.quantity, 1.75)
        self.assertEqual(line2.quantity, 0.75)
        self.assertEqual(len(line_1.subcontractor_work_ids), 2)
        admin_subcontractor = line_1.subcontractor_work_ids.filtered(
            lambda sub: sub.employee_id.user_id == self.admin_user
        )
        demo_sub = line_1.subcontractor_work_ids - admin_subcontractor
        self.assertEqual(admin_subcontractor.quantity, 0.25)
        self.assertEqual(demo_sub.quantity, 1.5)
        self.assertEqual(demo_sub.cost_price, 675.0)

        line_ids = [self.line_7.id]
        self._create_invoice(line_ids=line_ids)
        # due to fucked up mess we delete and create a new invoice line instead
        # of updating the existing one... so we do not use the original line2 variable
        # Maybe we'll solve this in the future
        line2 = invoice.invoice_line_ids - line_1
        self.assertEqual(line2.quantity, 1.25)
        self.assertEqual(len(line2.subcontractor_work_ids.timesheet_line_ids), 2)
        self.assertEqual(line2.subcontractor_work_ids.quantity, 1.25)
        self.assertEqual(line2.subcontractor_work_ids.cost_price, 562.5)

        # test line label
        self.assertIn(line_1.task_id.name, line_1.name)
        self.assertIn(line2.task_id.name, line2.name)

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

    def test_supplier_invoice(self):
        # quick test for not finished feature, this should be improved along
        # with the supplier invoice feature
        expense_account = self.env["account.account"].create(
            {
                "code": "611111",
                "name": "test expense account",
                "user_type_id": self.env.ref("account.data_account_type_expenses").id,
            }
        )
        internal_project = self.project.copy(
            {
                "invoicing_mode": "supplier",
                "supplier_invoice_account_expense_id": expense_account.id,
                "supplier_invoice_price_unit": 450,
            }
        )
        line_ids = [self.line_4.id, self.line_5.id]
        wizard = (
            self.env["supplier.timesheet.invoice"]
            .with_context(active_ids=line_ids)
            .create(
                {
                    "partner_id": self.partner.id,
                    "create_invoice": True,
                    "force_project_id": internal_project.id,
                }
            )
        )
        action = wizard.action_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line1 = invoice.invoice_line_ids.filtered(
            lambda li: li.task_id == self.line_4.task_id
        )
        self.assertEqual(line1.price_unit, 450)
        self.assertEqual(line1.quantity, 0.5)

        line_ids = [self.line_3.id]
        wizard = (
            self.env["supplier.timesheet.invoice"]
            .with_context(active_ids=line_ids)
            .create(
                {
                    "partner_id": self.partner.id,
                    "invoice_id": invoice.id,
                    "force_project_id": internal_project.id,
                    "create_invoice": False,
                }
            )
        )
        wizard.action_invoice()
        line1 = invoice.invoice_line_ids.filtered(
            lambda li: li.task_id == self.line_4.task_id
        )
        self.assertEqual(line1.quantity, 1.5)
        self.assertEqual(line1.price_unit, 450)
