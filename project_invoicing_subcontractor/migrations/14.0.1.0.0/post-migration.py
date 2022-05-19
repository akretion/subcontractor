# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.logged_query(
        env.cr,
        """
            UPDATE account_analytic_line
            SET
                invoice_line_id = aml.id
            FROM account_invoice_line ail
            JOIN account_move_line aml ON aml.old_invoice_line_id = ail.id
            WHERE account_analytic_line.old_invoice_line_id = ail.id
            AND account_analytic_line.old_invoice_line_id IS NOT NULL
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
            UPDATE account_analytic_line
            SET
                invoice_id = am.id
            FROM account_invoice ai
            JOIN account_move am ON am.old_invoice_id = ai.id
            WHERE account_analytic_line.old_invoice_id = ai.id
            AND account_analytic_line.old_invoice_id IS NOT NULL
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
            UPDATE account_analytic_line
            SET
                supplier_invoice_line_id = aml.id
            FROM account_invoice_line ail
            JOIN account_move_line aml ON aml.old_invoice_line_id = ail.id
            WHERE account_analytic_line.old_supplier_invoice_line_id = ail.id
            AND account_analytic_line.old_supplier_invoice_line_id IS NOT NULL
        """,
    )
