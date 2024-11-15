def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_move
        SET enough_project_amount = enough_analytic_amount
        WHERE enough_analytic_amount = true
    """
    )
