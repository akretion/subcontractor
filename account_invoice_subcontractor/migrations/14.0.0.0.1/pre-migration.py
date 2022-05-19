# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # Rename column so we keep the data but leave the update of the module create
    # a new column with a foreign key towards account.move
    # in post migration we'll manage the migraiton of the data from old field to new one
    openupgrade.logged_query(
        env.cr,
        """
            ALTER TABLE subcontractor_work
            RENAME COLUMN invoice_line_id TO old_invoice_line_id;
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
            ALTER TABLE subcontractor_work
            RENAME COLUMN invoice_id TO old_invoice_id;
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
            ALTER TABLE subcontractor_work
            RENAME COLUMN supplier_invoice_line_id TO old_supplier_invoice_line_id;
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
            ALTER TABLE subcontractor_work
            RENAME COLUMN supplier_invoice_id TO old_supplier_invoice_id;
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
            ALTER TABLE subcontractor_work
            RENAME COLUMN subcontractor_invoice_line_id TO old_subcontractor_invoice_line_id;
        """,
    )
