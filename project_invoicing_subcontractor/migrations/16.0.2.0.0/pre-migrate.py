def migrate(cr, version):
    cr.execute("ALTER TABLE account_move ADD COLUMN enough_project_amount bool")
