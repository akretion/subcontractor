# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, timedelta

from odoo.tests.common import Form

from odoo.addons.account_invoice_inter_company.tests.test_inter_company_invoice import (
    TestAccountInvoiceInterCompanyBase,
)


class TestSubcontractorInvoice(TestAccountInvoiceInterCompanyBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_obj = cls.env["account.account"]
        cls.invoice_obj = cls.env["account.move"]

        # configure subcontracted product
        cls.product_consultant_multi_company.write({"subcontracted": True})
        cls.product_consultant_multi_company.sudo(cls.user_company_b.id).write(
            {"property_account_income_id": cls.a_sale_company_b.id}
        )

        # Create sale journal for company B as it was not done in
        # account_invoice_inter_company module
        cls.env["account.journal"].create(
            {
                "name": "Sale journal - Company B",
                "code": "SAJ-B",
                "type": "sale",
                # "sequence_id": cls.sequence_sale_journal_company_b.id,
                # "update_posted": True,
                "company_id": cls.company_b.id,
            }
        )

        # Create purchase journal for company A as it was not done in
        # account_invoice_inter_company module
        cls.env["account.journal"].create(
            {
                "name": "Purchases Journal - (Company A)",
                "code": "EXJ-A",
                "type": "purchase",
                # "sequence_id": cls.sequence_purchase_journal_company_a.id,
                # "update_posted": True,
                "company_id": cls.company_a.id,
            }
        )

        cls.customer_a = cls.env["res.partner"].create({"name": "Customer A"})
        cls.employee_b = cls.env["hr.employee"].create(
            {
                "name": "Employee B",
                "subcontractor_type": "internal",
                "commission_rate": "10.0",
                "company_id": cls.company_a.id,
                "subcontractor_company_id": cls.company_b.id,
                "user_id": cls.user_company_b.id,
            }
        )
        # subcontracted_user should have the subcontractor rights (this part should
        # may be change...)
        is_subcontractor = cls.env.ref(
            "account_invoice_subcontractor.group_is_subcontractor"
        )
        cls.user_company_b.write({"groups_id": [(4, is_subcontractor.id, 0)]})
        categ = cls.env.ref("product.product_category_3")
        categ.with_context(
            force_company=cls.company_a.id
        ).property_account_expense_categ_id = cls.a_expense_company_a.id

    def test_customer_subcontractor(self):
        """Company A sell stuff to customer B but subcontract it to company B"""
        # ensure our user is in company A
        self.env.user.company_id = self.company_a.id

        invoice = Form(
            self.account_move_obj.with_company(self.company_a.id).with_context(
                default_move_type="out_invoice",
            )
        )
        invoice.partner_id = self.partner_company_b
        invoice.invoice_date = date.today() - timedelta(days=20)
        invoice.journal_id = self.sales_journal_company_a
        invoice.currency_id = self.env.ref("base.EUR")

        with invoice.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product_consultant_multi_company
            line_form.quantity = 2
            line_form.product_uom_id = self.env.ref("uom.product_uom_hour")
            line_form.account_id = self.a_sale_company_a
            line_form.name = self.product_consultant_multi_company.name
            line_form.price_unit = 200.0
        invoice = invoice.save()
        invoice_line = invoice.invoice_line_ids[0]
        assert invoice_line.quantity == 2
        assert invoice_line.price_unit == 200.0
        sub_work_vals = {
            "employee_id": self.employee_b.id,
            "invoice_line_id": invoice_line.id,
        }
        sub_work_vals = self.env["subcontractor.work"].play_onchanges(
            sub_work_vals, ["employee_id"]
        )
        subwork = self.env["subcontractor.work"].create(sub_work_vals)
        self.assertEqual(subwork.quantity, 2)
        self.assertEqual(subwork.sale_price_unit, 200)
        self.assertEqual(subwork.cost_price_unit, 180)
        self.assertEqual(subwork.cost_price, 360)
        self.assertEqual(subwork.sale_price, 400)
        assert invoice.payment_state != "paid"
        invoice.action_post()
        assert invoice.amount_residual > 0
        self.assertEqual(subwork.state, "posted")
        # cron is lauched by odoobot (user=1, super admin)
        # self.env = self.env(user=self.env['res.users'])
        self.env[
            "subcontractor.work"
        ].sudo()._scheduler_action_subcontractor_invoice_create()
        invoice_b = self.env["account.move"].search(
            [("company_id", "=", self.company_b.id), ("move_type", "=", "out_invoice")]
        )
        self.assertEqual(len(invoice_b), 1)
        self.assertEqual(invoice_b.amount_untaxed, 360)
        self.assertEqual(
            invoice_b.invoice_line_ids.subcontractor_work_invoiced_id, subwork
        )

        invoice_c = self.env["account.move"].search(
            [
                ("company_id", "=", self.company_a.id),
                ("move_type", "=", "in_invoice"),
                ("auto_invoice_id", "=", invoice_b.id),
            ]
        )
        self.assertEqual(len(invoice_c), 1)
        self.assertEqual(invoice_c.amount_untaxed, 360)
        self.assertEqual(
            invoice_c.invoice_line_ids.subcontractor_work_invoiced_id, subwork
        )
