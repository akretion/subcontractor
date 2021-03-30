# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, timedelta

from odoo.modules.module import get_resource_path
from odoo.tests.common import SavepointCase
from odoo.tools import convert_file


class TestSubcontractorInvoice(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # use account_invoice_inter_company data to avoid recreating a new company
        # and all stuff that goes with it.
        module = "account_invoice_inter_company"
        convert_file(
            cls.cr,
            module,
            get_resource_path(module, "tests", "inter_company_invoice.xml"),
            None,
            "init",
            False,
            "test",
            cls.registry._assertion_report,
        )
        cls.account_obj = cls.env["account.account"]
        cls.invoice_obj = cls.env["account.invoice"]
        cls.invoice_company_a = cls.env.ref(
            "account_invoice_inter_company.customer_invoice_company_a"
        )
        cls.user_company_a = cls.env.ref("account_invoice_inter_company.user_company_a")
        cls.user_company_b = cls.env.ref("account_invoice_inter_company.user_company_b")

        cls.company_a = cls.env.ref("account_invoice_inter_company.company_a")
        cls.company_b = cls.env.ref("account_invoice_inter_company.company_b")

        # configure subcontracted product
        cls.subcontracted_product = cls.env.ref(
            "account_invoice_inter_company.product_consultant_multi_company"
        )
        cls.subcontracted_product.write({"subcontracted": True})
        cls.subcontracted_product.sudo(cls.user_company_b.id).write(
            {
                "property_account_income_id": cls.env.ref(
                    "account_invoice_inter_company.a_sale_company_b"
                ).id
            }
        )

        # Create sale journal for company B as it was not done in
        # account_invoice_inter_company module
        cls.env["account.journal"].create(
            {
                "name": "Sale journal - Company B",
                "code": "SAJ-B",
                "type": "sale",
                "sequence_id": cls.env.ref(
                    "account_invoice_inter_company.sequence_sale_journal_company_b"
                ).id,
                "update_posted": True,
                "company_id": cls.company_b.id,
            }
        )

        # Create purchase journal for  company A as it was not done in
        # account_invoice_inter_company module
        cls.env["account.journal"].create(
            {
                "name": "Purchases Journal - (Company A)",
                "code": "EXJ-A",
                "type": "purchase",
                "sequence_id": cls.env.ref(
                    "account_invoice_inter_company.sequence_purchase_journal_company_a"
                ).id,
                "update_posted": True,
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
        ).property_account_expense_categ_id = cls.env.ref(
            "account_invoice_inter_company.a_expense_company_a"
        ).id

    def test_customer_subcontractor(self):
        """ Company A sell stuff to customer B but subcontract it to company B """
        # ensure our user is in company A
        self.env.user.company_id = self.company_a.id
        # ensure cron will take it
        date_invoice = date.today() - timedelta(days=20)

        invoice = self.env["account.invoice"].create(
            {
                "type": "out_invoice",
                "date_invoice": date_invoice,
                "partner_id": self.customer_a.id,
                "account_id": self.env.ref(
                    "account_invoice_inter_company.a_recv_company_a"
                ).id,
                "company_id": self.company_a.id,
            }
        )
        invoice_line = self.env["account.invoice.line"].create(
            {
                "product_id": self.subcontracted_product.id,
                "name": self.subcontracted_product.name,
                "account_id": self.env.ref(
                    "account_invoice_inter_company.a_sale_company_a"
                ).id,
                "price_unit": 200,
                "quantity": 2,
                "company_id": self.company_a.id,
                "invoice_id": invoice.id,
            }
        )

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

        invoice.action_invoice_open()
        self.assertEqual(subwork.state, "open")
        # cron is lauched by odoobot (user=1, super admin)
        # self.env = self.env(user=self.env['res.users'])
        self.env[
            "subcontractor.work"
        ].sudo()._scheduler_action_subcontractor_invoice_create()
        invoice_b = self.env["account.invoice"].search(
            [("company_id", "=", self.company_b.id), ("type", "=", "out_invoice")]
        )
        self.assertEqual(len(invoice_b), 1)
        self.assertEqual(invoice_b.amount_untaxed, 360)
        self.assertEqual(
            invoice_b.invoice_line_ids.subcontractor_work_invoiced_id, subwork
        )
        invoice_b.with_context(test_account_invoice_inter_company=True).sudo(
            self.user_company_b.id
        ).action_invoice_open()

        invoice_c = self.env["account.invoice"].search(
            [
                ("company_id", "=", self.company_a.id),
                ("type", "=", "in_invoice"),
                ("auto_invoice_id", "=", invoice_b.id),
            ]
        )
        self.assertEqual(len(invoice_c), 1)
        self.assertEqual(invoice_c.amount_untaxed, 360)
        self.assertEqual(
            invoice_c.invoice_line_ids.subcontractor_work_invoiced_id, subwork
        )
