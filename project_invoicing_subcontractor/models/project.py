# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

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
    prepaid_available_amount = fields.Monetary(compute="_compute_prepaid_amount")
    prepaid_total_amount = fields.Monetary(compute="_compute_prepaid_amount")
    # Not sure  we really need this.
    #    price_unit = fields.Float(compute="_compute_price_unit")
    #
    #    @api.depends("partner_id", "invoicing_typology_id")
    #    def _compute_price_unit(self):
    #        for project in self:
    #            price = project._get_sale_price_unit()
    #            if project.invoicing_mode == "customer_postpaid":
    #                project.price_unit = price
    #            elif project.invoicing_mode == "customer_prepaid":
    #                contribution = project.company_id.with_context(partner=partner).\
    # _get_commission_rate()
    #                project.price_unit = (1-contribution) = price
    #            else:
    #                project.price_unit = 0.0
    #

    @api.depends(
        "invoicing_mode",
        "analytic_account_id",
        "analytic_account_id.account_move_line_ids.prepaid_is_paid",
    )
    def _compute_prepaid_amount(self):
        for project in self:
            total_amount = 0
            available_amount = 0
            if project.invoicing_mode == "customer_prepaid":
                (
                    move_lines,
                    paid_lines,
                ) = project.analytic_account_id._prepaid_move_lines()
                total_amount = -sum(move_lines.mapped("amount_currency")) or 0.0
                available_amount = -sum(paid_lines.mapped("amount_currency")) or 0.0
            project.prepaid_total_amount = total_amount
            project.prepaid_available_amount = available_amount

    @api.depends("force_uom_id", "invoicing_typology_id")
    def _compute_uom_id(self):
        for project in self:
            if project.force_uom_id:
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
        price = product.with_context(
            pricelist=partner.property_product_pricelist.id,
            partner=partner.id,
            uom=self.uom_id.id,
        ).price
        return price

    @api.constrains("invoicing_mode", "analytic_account_id")
    def _check_analytic_account(self):
        for project in self:
            if (
                project.invoicing_mode == "customer_prepaid"
                and not project.analytic_account_id
            ):
                raise UserError(
                    _(
                        "The analytic account is mandatory on project configured with "
                        "prepaid invoicing"
                    )
                )

    @api.constrains("analytic_account_id", "partner_id", "invoicing_mode")
    def _check_analytic_account_consistency(self):
        for project in self:
            if project.analytic_account_id and not all(
                x == project.analytic_account_id.project_ids.partner_id[0]
                for x in project.analytic_account_id.project_ids.partner_id
            ):
                raise UserError(
                    _(
                        "All projects linked to a same analytic account has to have the "
                        "same customer."
                    )
                )
            if project.analytic_account_id and not all(
                x == project.analytic_account_id.project_ids.mapped("invoicing_mode")[0]
                for x in project.analytic_account_id.project_ids.mapped(
                    "invoicing_mode"
                )
            ):
                raise UserError(
                    _(
                        "All projects linked to a same analytic account has to have the "
                        "same invoicing mode."
                    )
                )

    def action_project_prepaid_move_line(self):
        self.ensure_one()
        action = self.env.ref("account.action_account_moves_all_tree").sudo().read()[0]
        move_lines, paid_lines = self.analytic_account_id._prepaid_move_lines()
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


class ProjectTask(models.Model):
    _inherit = "project.task"

    invoiceable_hours = fields.Float(compute="_compute_invoiceable", store=True)
    invoiceable_days = fields.Float(compute="_compute_invoiceable", store=True)
    invoice_line_ids = fields.One2many("account.move.line", "task_id", "Invoice Line")

    @api.depends("timesheet_ids.discount", "timesheet_ids.unit_amount")
    def _compute_invoiceable(self):
        for record in self:
            total = 0
            for line in record.timesheet_ids:
                total += line.unit_amount * (1 - line.discount / 100.0)
            record.invoiceable_hours = total
            record.invoiceable_days = record.project_id.convert_hours_to_days(total)

    # TODO we should move this in a generic module
    # changing the project on the task should be propagated
    # on the analytic line to avoid issue during invoicing
    def write(self, vals):
        res = super().write(vals)
        if "project_id" in vals:
            if not vals["project_id"]:
                raise UserError(
                    _(
                        "The project can not be removed, "
                        "please remove the timesheet first"
                    )
                )
            else:
                project = self.env["project.project"].browse(vals["project_id"])
                vals = {
                    "project_id": project.id,
                    "account_id": project.analytic_account_id.id,
                }
            self.mapped("timesheet_ids").write(vals)
        return res
