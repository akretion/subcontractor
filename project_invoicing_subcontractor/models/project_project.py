# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    def _prepaid_move_lines(self):
        self.ensure_one()
        move_lines = self.env["account.move.line"].search(
            [
                ("project_id", "=", self.id),
                ("account_id.is_prepaid_account", "=", True),
                ("parent_state", "=", "posted"),
            ],
        )
        paid_lines = move_lines.filtered(
            lambda line: line.prepaid_is_paid
            or (
                line.move_id.supplier_invoice_ids
                and all(
                    [
                        x.to_pay and x.payment_state != "paid"
                        for x in line.move_id.supplier_invoice_ids
                    ]
                )
            )
        )
        return move_lines, paid_lines

    def _get_allowed_uom_ids(self):
        return [
            self.env.ref("uom.product_uom_hour").id,
            self.env.ref("uom.product_uom_day").id,
        ]

    def _get_force_uom_id_domain(self):
        return [("id", "in", self._get_allowed_uom_ids())]

    invoicing_typology_id = fields.Many2one(
        "project.invoice.typology", check_company=True
    )
    force_uom_id = fields.Many2one(
        "uom.uom",
        "Force Unit",
        domain=_get_force_uom_id_domain,
        help="If empty, the unit of measure will be taken on the product use for "
        "invoicing (usuallly in day)",
    )
    uom_id = fields.Many2one("uom.uom", compute="_compute_uom_id", store=True)
    hour_uom_id = fields.Many2one(
        help="The default hour uom considers there are 8H in a day of work. If it is "
        "different for your project, choose an other uom with a different "
        "conversion, like 7h/day. \n Odoo will use this to convert the work "
        "amount in hour to a number of day in the invoice."
    )
    invoicing_mode = fields.Selection(
        related="invoicing_typology_id.invoicing_mode", store=True
    )
    supplier_invoice_price_unit = fields.Float(
        "Force Unit Price",
        help="For customer prepaid project, the price in the subcontractor invoice is "
        "computed from the customer sale price and reduced by the akretion "
        "contribution. If you want to force a different price, you can use this "
        "field to set a price net of Akretion contribution.\n"
        "If this is an akretion project, the price is mandatory, and is also "
        "net of the akretion contribution",
    )
    price_unit = fields.Float(compute="_compute_price_unit")
    prepaid_move_line_ids = fields.One2many(
        "account.move.line",
        "project_id",
        domain=[("is_prepaid_line", "=", True)],
    )

    available_amount = fields.Monetary(compute="_compute_prepaid_amount")
    prepaid_total_amount = fields.Monetary(compute="_compute_prepaid_amount")
    prepaid_available_amount = fields.Monetary(compute="_compute_prepaid_amount")
    not_invoiced_timesheet_amount = fields.Monetary(compute="_compute_prepaid_amount")
    # technical field used for display
    project_health_state = fields.Selection(
        [("high", "High"), ("medium", "Medium"), ("low", "Low")],
        compute="_compute_prepaid_amount",
    )

    def _get_supplier_draft_invoice_amount(self):
        self.ensure_one()
        amount = 0.0
        if self.invoicing_mode != "customer_prepaid":
            return amount
        draft_inv_lines = self.env["account.move.line"].search(
            [
                ("move_id.move_type", "=", "in_invoice"),
                ("move_id.state", "=", "draft"),
                ("project_id", "=", self.id),
            ]
        )
        if draft_inv_lines:
            amount = sum(draft_inv_lines.mapped("contribution_price_subtotal"))
        return amount

    @api.depends("prepaid_move_line_ids.prepaid_is_paid")
    def _compute_prepaid_amount(self):
        for project in self:
            # draft supplier invoiced not validated yet, we want to deduce it form the
            # available amounts we show...
            supplier_draft_invoice_amount = project._get_supplier_draft_invoice_amount()
            move_lines, paid_lines = project._prepaid_move_lines()
            available_if_paid = -sum(move_lines.mapped("amount_currency")) or 0.0
            available_if_paid -= supplier_draft_invoice_amount
            immediatly_available_amount = (
                -sum(paid_lines.mapped("amount_currency")) or 0.0
            )
            not_paid_lines = move_lines - paid_lines
            supplier_not_paid = not_paid_lines.filtered(
                # ignore customer invoice with negative line when deducting what has
                # not been paid
                lambda line: line.amount_currency > 0.0
                and line.move_id.move_type != "out_invoice"
            )
            immediatly_available_amount -= sum(
                supplier_not_paid.mapped("amount_currency")
            )
            immediatly_available_amount -= supplier_draft_invoice_amount
            project.prepaid_total_amount = available_if_paid
            # this one is used for display/info, so we show what is really available
            # as if all supplier invoices were paid.
            project.prepaid_available_amount = immediatly_available_amount
            # Keep available_amount without to_pay supplier invoices neither ongoing
            # supplier invoices because it is used to make them to pay.
            project.available_amount = (
                -sum(
                    move_lines.filtered(lambda m: m.prepaid_is_paid).mapped(
                        "amount_currency"
                    )
                )
                or 0.0
            )
            # timesheet amount
            ts_amount = 0.0
            to_invoice_timesheets = self.env["account.analytic.line"].search(
                [
                    ("invoiceable_amount", ">", 0.0),
                    ("invoice_id", "=", False),
                    ("project_id", "=", project.id),
                    ("project_id.invoicing_typology_id", "!=", False),
                ]
            )
            if to_invoice_timesheets:
                invoiceable_time = (
                    to_invoice_timesheets._get_invoiceable_qty_with_project_unit()
                )
                ts_amount = invoiceable_time * project.price_unit
            project.not_invoiced_timesheet_amount = ts_amount
            if available_if_paid < ts_amount:
                health = "low"
            elif immediatly_available_amount < ts_amount:
                health = "medium"
            else:
                health = "high"
            project.project_health_state = health

    @api.depends(
        "partner_id", "invoicing_typology_id", "uom_id", "supplier_invoice_price_unit"
    )
    def _compute_price_unit(self):
        for project in self:
            if (
                project.supplier_invoice_price_unit
                and project.invoicing_mode != "customer_postpaid"
            ):
                project.price_unit = project.supplier_invoice_price_unit
            elif project.invoicing_mode in ["customer_postpaid", "customer_prepaid"]:
                price = project._get_sale_price_unit()
                project.price_unit = price
            else:
                project.price_unit = 0.0

    @api.depends("force_uom_id", "invoicing_typology_id")
    def _compute_uom_id(self):
        for project in self:
            # Force day if not customer postpaid it makes no sense to use other uom
            # Edit 26-08-2024 I add supplier, maybe we can do it for all invoicing mode
            if project.invoicing_mode not in ["customer_postpaid", "supplier"]:
                uom_id = self.env.ref("uom.product_uom_day").id
            elif project.force_uom_id:
                uom_id = project.force_uom_id.id
            elif (
                project.invoicing_typology_id.product_id.uom_id.id
                in self._get_allowed_uom_ids()
            ):
                uom_id = project.invoicing_typology_id.product_id.uom_id.id
            else:
                uom_id = False
            project.uom_id = uom_id

    def _get_project_invoicing_product(self):
        self.ensure_one()
        return self.invoicing_typology_id.product_id

    def _get_sale_price_unit(self):
        self.ensure_one()
        product = self._get_project_invoicing_product()
        partner = self.partner_id
        pricelist = partner.property_product_pricelist
        if pricelist:
            price = pricelist._get_product_price(product, 1, uom=self.uom_id)
        else:
            price = product.list_price
        return price

    def action_project_prepaid_move_line(self):
        self.ensure_one()
        action = self.env.ref("account.action_account_moves_all_tree").sudo().read()[0]
        move_lines, paid_lines = self._prepaid_move_lines()
        if self.env.context.get("prepaid_is_paid"):
            move_lines = paid_lines
        action["domain"] = [("id", "in", move_lines.ids)]
        action["context"] = {
            "search_default_group_by_account": 1,
            "create": False,
            "edit": False,
            "delete": False,
        }
        return action

    def action_project_timesheet_lines(self):
        self.ensure_one()
        action = self.env.ref("hr_timesheet.timesheet_action_all").sudo().read()[0]
        to_invoice_timesheets = self.env["account.analytic.line"].search(
            [
                ("invoiceable_amount", ">", 0.0),
                ("invoice_id", "=", False),
                ("project_id", "=", self.id),
                ("project_id.invoicing_typology_id", "!=", False),
            ]
        )
        action["domain"] = [("id", "in", to_invoice_timesheets.ids)]
        action["context"] = {
            "search_default_to_invoice": 1,
            "create": False,
            "edit": False,
            "delete": False,
        }
        return action
