# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.tests import common


class TestAccountProjectPolicy(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.project = cls.env["project.project"].create({"name": "Test Project"})
        cls.account = cls.env["account.account"].create(
            {
                "name": "Test Account",
                "code": "666666",
                "account_type": "expense",
            }
        )
        # Journal pour les écritures
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.env.company.id)], limit=1
        )

    def test_project_policy_always(self):
        self.account.project_policy = "always"
        with self.assertRaises(ValidationError):
            self.env["account.move"].create(
                {
                    "journal_id": self.journal.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": self.account.id,
                                "name": "Line without project",
                                "debit": 100.0,
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": self.account.id,
                                "name": "Counterpart",
                                "credit": 100.0,
                            },
                        ),
                    ],
                }
            )

    def test_project_policy_never(self):
        self.account.project_policy = "never"
        with self.assertRaises(ValidationError):
            self.env["account.move"].create(
                {
                    "journal_id": self.journal.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": self.account.id,
                                "name": "Line with project",
                                "project_id": self.project.id,
                                "debit": 100.0,
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": self.account.id,
                                "name": "Counterpart",
                                "credit": 100.0,
                            },
                        ),
                    ],
                }
            )

    def test_project_policy_posted(self):
        self.account.project_policy = "posted"
        move = self.env["account.move"].create(
            {
                "journal_id": self.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account.id,
                            "name": "Draft line",
                            "debit": 100.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account.id,
                            "name": "Counterpart",
                            "credit": 100.0,
                        },
                    ),
                ],
            }
        )
        with self.assertRaises(ValidationError):
            move.action_post()
