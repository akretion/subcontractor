# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoicing(AccountTestInvoicingCommon):
    def mref(self, xml):
        return self.env.ref("project_invoicing_subcontractor.%s" % xml)

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        # we use AccountTestInvoicingCommon to initialte other companies but still
        # want to work in main company
        cls.admin_user = cls.env.ref("base.user_admin")
        cls.env = cls.env(user=cls.admin_user)
        cls.employee_admin = cls.env.ref("hr.employee_admin")
        cls.employee_admin.write(
            {"subcontractor_company_id": cls.company_data["company"].id}
        )
        cls.env.company.write({"commission_rate": 10.0})
        cls.env.ref("hr.employee_qdp").write({"subcontractor_type": "external"})
        cls.demo_partner = cls.env.ref("base.partner_demo")
        cls.admin_company_partner = cls.company_data["company"].partner_id
        cls.line_1 = cls.mref(cls, "account_analytic_line_1")
        cls.line_2 = cls.mref(cls, "account_analytic_line_2")
        cls.line_3 = cls.mref(cls, "account_analytic_line_3")
        cls.line_4 = cls.mref(cls, "account_analytic_line_4")
        cls.line_5 = cls.mref(cls, "account_analytic_line_5")
        cls.line_6 = cls.mref(cls, "account_analytic_line_6")
        cls.line_7 = cls.mref(cls, "account_analytic_line_7")

        cls.line_1_2 = cls.mref(cls, "account_analytic_line_1_proj2")
        cls.line_2_2 = cls.mref(cls, "account_analytic_line_2_proj2")
        cls.line_3_2 = cls.mref(cls, "account_analytic_line_3_proj2")
        cls.line_4_2 = cls.mref(cls, "account_analytic_line_4_proj2")
        cls.line_5_2 = cls.mref(cls, "account_analytic_line_5_proj2")
        cls.line_6_2 = cls.mref(cls, "account_analytic_line_6_proj2")
        cls.line_7_2 = cls.mref(cls, "account_analytic_line_7_proj2")

        cls.line_1_4 = cls.mref(cls, "account_analytic_line_1_4")
        cls.line_2_4 = cls.mref(cls, "account_analytic_line_2_4")
        cls.line_3_4 = cls.mref(cls, "account_analytic_line_3_4")
        cls.line_4_4 = cls.mref(cls, "account_analytic_line_4_4")

        cls.partner = cls.env.ref("base.res_partner_4")
        cls.product = cls.mref(cls, "product_product_1")
        cls.day_uom = cls.env.ref("uom.product_uom_day")
        cls.hour_uom = cls.env.ref("uom.product_uom_hour")
        cls.project = cls.mref(cls, "project_project_1")
        cls.project2 = cls.mref(cls, "project_project_2")

        cls.maintenance_product = cls.mref(cls, "product_product_2")

    def _create_invoicing_wizard(self, line_ids=None, invoice=None):
        line_ids = line_ids or [self.line_3.id, self.line_4.id, self.line_5.id]
        wizard = (
            self.env["subcontractor.timesheet.invoice"]
            .with_context(active_ids=line_ids)
            .create(
                {
                    "invoice_id": invoice and invoice.id or False,
                    "create_invoice": not invoice and True or False,
                }
            )
        )
        return wizard

    def _create_customer_invoice(self, line_ids=None, invoice=False):
        wizard = self._create_invoicing_wizard(line_ids=line_ids, invoice=invoice)
        action = wizard.action_customer_invoice()
        return self._get_invoices_from_wizard_action(action)

    def _get_invoices_from_wizard_action(self, action):
        if action.get("res_id"):
            invoices = self.env["account.move"].browse(action["res_id"])
        else:
            invoices = self.env["account.move"].search(action["domain"])
        return invoices

    def _create_supplier_invoice(self, line_ids=None, invoice=False):
        wizard = self._create_invoicing_wizard(line_ids=line_ids, invoice=invoice)
        action = wizard.action_supplier_invoice()
        return self._get_invoices_from_wizard_action(action)

    def test_invoicing_in_days(self):
        invoice = self._create_customer_invoice()
        self.assertEqual(invoice.amount_untaxed, 1125)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line_1 = invoice.invoice_line_ids[0]
        self.assertEqual(line_1.quantity, 1.5)
        self.assertEqual(line_1.price_unit, 500)
        self.assertEqual(line_1.product_uom_id, self.day_uom)
        self.assertEqual(line_1.product_id, self.product)
        self.assertTrue(line_1.tax_ids)

    def test_invoicing_in_hours(self):
        self.project.force_uom_id = self.hour_uom
        invoice = self._create_customer_invoice()
        self.assertEqual(invoice.amount_untaxed, 1125)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line_1 = invoice.invoice_line_ids[0]
        self.assertEqual(line_1.quantity, 12)
        self.assertEqual(line_1.price_unit, 62.5)
        self.assertEqual(line_1.product_uom_id, self.hour_uom)
        self.assertEqual(line_1.product_id, self.product)

    def test_invoicing_with_discount(self):
        self.line_3.discount = 50
        self.project.force_uom_id = self.hour_uom
        invoice = self._create_customer_invoice()
        self.assertEqual(invoice.amount_untaxed, 875)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        line_1 = invoice.invoice_line_ids[0]
        self.assertEqual(line_1.quantity, 8)
        self.assertEqual(line_1.price_unit, 62.5)
        self.assertEqual(line_1.product_uom_id, self.hour_uom)
        self.assertEqual(line_1.product_id, self.product)

    def test_invoicing_update_multiple_employee(self):
        line_ids = [self.line_6.id, self.line_3.id, self.line_4.id, self.line_5.id]
        invoice = self._create_customer_invoice(line_ids=line_ids)
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
        self._create_customer_invoice(line_ids=line_ids, invoice=invoice)
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

    def _create_prepaid_customer_invoice(self, quantity, project):
        invoice = (
            self.env["account.move"]
            .with_context(default_move_type="out_invoice")
            .create(
                {
                    "partner_id": self.partner.id,
                    "invoice_date": date.today(),
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.maintenance_product.id,
                                "quantity": quantity,
                                "product_uom_id": self.env.ref(
                                    "uom.product_uom_hour"
                                ).id,
                                "project_id": project.id,
                                "name": self.maintenance_product.name,
                            }
                        )
                    ],
                }
            )
        )
        return invoice

    def test_prepaid_invoicing_process_same_project(self):
        invoice = self._create_prepaid_customer_invoice(10, self.line_5_2.project_id)
        self.assertTrue(invoice.invoice_line_ids.tax_ids)
        invoice.action_post()
        self.assertEqual(invoice.invoice_line_ids.account_id.code, "418101")

        #
        line_ids = [self.line_5_2.id, self.line_6_2.id, self.line_7_2.id]
        sup_invoices = self._create_supplier_invoice(line_ids=line_ids)
        demo_invoice = sup_invoices.filtered(
            lambda i: i.partner_id == self.demo_partner
        )
        admin_invoice = sup_invoices.filtered(
            lambda i: i.partner_id == self.admin_company_partner
        )
        self.assertEqual(demo_invoice.customer_id.id, self.project2.partner_id.id)
        demo_invoice.action_post()
        self.assertEqual(len(demo_invoice.invoice_line_ids), 1)
        self.assertEqual(demo_invoice.invoice_line_ids[0].account_id.code, "611150")
        self.assertEqual(demo_invoice.amount_untaxed, 675.0)

        misc_move = demo_invoice.prepaid_countdown_move_id
        self.assertEqual(misc_move.state, "posted")
        misc_prepaid_line = misc_move.line_ids.filtered(
            lambda line: line.account_id.code == "418101"
        )
        self.assertEqual(misc_prepaid_line.debit, 750.0)

        # demo invoice of 10H is validated, admin not, so it won't be taken into account
        # by the to pay cron
        self.env["account.move"].compute_enought_project_amount()
        self.assertFalse(demo_invoice.to_pay)
        self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move"
        ).create({})._create_payments()
        self.env["account.move"].compute_enought_project_amount()
        self.assertTrue(demo_invoice.to_pay)

        # set admin invoice one day later to be sure demo invoice has priority
        # Add customer invoice so there is enough amount to validate the admin invoice
        # but it is not paid
        customer_invoice2 = self._create_prepaid_customer_invoice(
            1.99, self.line_5_2.project_id
        )
        customer_invoice2.action_post()
        customer_invoice3 = self._create_prepaid_customer_invoice(
            0.01, self.line_5_2.project_id
        )
        customer_invoice3.action_post()
        admin_invoice.write({"invoice_date": date.today() + timedelta(days=1)})
        admin_invoice.action_post()
        self.env["account.move"].compute_enought_project_amount()
        self.assertFalse(admin_invoice.to_pay)
        self.assertTrue(demo_invoice.to_pay)

        self.env["account.payment.register"].with_context(
            active_ids=customer_invoice2.ids, active_model="account.move"
        ).create({})._create_payments()
        self.env["account.move"].compute_enought_project_amount()
        self.assertFalse(admin_invoice.to_pay)
        self.env["account.payment.register"].with_context(
            active_ids=customer_invoice3.ids, active_model="account.move"
        ).create({})._create_payments()
        self.env["account.move"].compute_enought_project_amount()
        self.assertTrue(admin_invoice.to_pay)
        self.assertTrue(demo_invoice.to_pay)

    def test_prepaid_invoicing_multiple_project_multiple_employee(self):
        self.line_6_2.project_id.supplier_invoice_price_unit = 700
        wizard_form = Form(
            self.env["subcontractor.timesheet.invoice"].with_context(
                active_ids=(self.line_6_2 | self.line_7_2 | self.line_1).ids
            )
        )
        self.assertTrue(wizard_form.error)
        wizard_form.force_project_id = self.project2
        self.assertFalse(wizard_form.error)
        wizard = wizard_form.save()
        action = wizard.action_supplier_invoice()
        invoices = self._get_invoices_from_wizard_action(action)
        self.assertEqual(len(invoices), 2)
        demo_invoice = invoices.filtered(lambda i: i.partner_id == self.demo_partner)
        self.assertEqual(len(demo_invoice.invoice_line_ids), 2)
        self.assertEqual(demo_invoice.move_type, "in_invoice")
        self.assertEqual(demo_invoice.amount_untaxed, 472.5)
        self.assertEqual(self.line_7_2.invoice_id, demo_invoice)

        # check the to pay is done at invoice validation if amount available is
        # enough (without the need of the cron)
        customer_invoice = self._create_prepaid_customer_invoice(
            15, self.line_5_2.project_id
        )
        customer_invoice.action_post()
        self.env["account.payment.register"].with_context(
            active_ids=customer_invoice.ids, active_model="account.move"
        ).create({})._create_payments()
        demo_invoice.action_post()
        self.assertTrue(demo_invoice.to_pay)

    def test_change_task_project(self):
        project = self.env.ref("project.project_project_1")
        self.line_1.task_id.project_id = project
        self.assertEqual(self.line_1.project_id, project)
        self.assertEqual(self.line_1.account_id, project.analytic_account_id)

    def test_remove_task_project(self):
        with self.assertRaises(UserError):
            self.line_1.task_id.project_id = False

    def test_supplier_invoice(self):
        self.mref("project_project_4")
        line_ids = [self.line_1_4.id, self.line_2_4.id, self.line_3_4.id]
        invoices = self._create_supplier_invoice(line_ids=line_ids)
        self.assertEqual(len(invoices), 2)
        invoice_admin = invoices.filtered(
            lambda i: i.partner_id == self.admin_company_partner
        )
        self.assertEqual(len(invoice_admin.invoice_line_ids), 2)
        line1 = invoice_admin.invoice_line_ids.filtered(
            lambda li: li.task_id == self.line_2_4.task_id
        )
        self.assertEqual(line1.price_unit, 400)
        self.assertEqual(line1.quantity, 0.5)
        self.assertEqual(line1.account_id.code, "611160")

        line_ids = [self.line_4_4.id]
        wizard = (
            self.env["subcontractor.timesheet.invoice"]
            .with_context(active_ids=line_ids)
            .create({})
        )
        wizard.write({"create_invoice": False, "invoice_id": invoice_admin.id})
        wizard.action_supplier_invoice()
        line1 = invoice_admin.invoice_line_ids.filtered(
            lambda li: li.task_id == self.line_4_4.task_id
        )
        line2 = invoice_admin.invoice_line_ids - line1
        self.assertEqual(line2.price_subtotal, 300)
        self.assertEqual(line1.quantity, 1.25)
        self.assertEqual(line1.price_unit, 400)
        invoice_admin.action_post()
        self.assertEqual(self.line_2_4.invoice_id, invoice_admin)
        self.assertFalse(invoice_admin.prepaid_countdown_move_id)

    def test_write_unlink_invoiced(self):
        self._create_customer_invoice()
        with self.assertRaises(UserError):
            self.line_3.unit_amount = 1000
        with self.assertRaises(UserError):
            self.line_3.unlink()
