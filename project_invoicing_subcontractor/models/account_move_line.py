# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)


from odoo import _, api, exceptions, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    task_id = fields.Many2one("project.task")
    task_stage_id = fields.Many2one(
        "project.task.type", related="task_id.stage_id", store=True
    )
    timesheet_line_ids = fields.One2many(
        "account.analytic.line", "invoice_line_id", "Timesheet Line"
    )
    timesheet_error = fields.Char(compute="_compute_timesheet_qty", store=True)
    timesheet_qty = fields.Float(
        digits="Product Unit of Measure",
        compute="_compute_timesheet_qty",
        store=True,
    )
    task_invoiceable_days = fields.Float(
        related="task_id.invoiceable_days",
        digits="Product Unit of Measure",
        string="Task Days",
        help="Total days of the task, helper to check if you miss some timesheet",
    )
    is_prepaid_line = fields.Boolean(
        related="account_id.is_prepaid_account", store=True
    )
    prepaid_is_paid = fields.Boolean(compute="_compute_prepaid_is_paid", store=True)
    contribution_price_subtotal = fields.Float(
        compute="_compute_contribution_subtotal", store=True
    )

    @api.depends(
        "account_id",
        "move_id.payment_state",
        "move_id.supplier_invoice_ids.payment_state",
        "move_id.move_type",
        "move_id.state",
    )
    def _compute_prepaid_is_paid(self):
        for line in self:
            if not line.account_id.is_prepaid_account:
                continue
            move = line.move_id
            if move.state in ("draft", "cancel"):
                line.prepaid_is_paid = False
            elif move.move_type == "out_refund":
                line.prepaid_is_paid = True
            elif move.move_type == "out_invoice":
                if move.payment_state in ("paid", "reversed"):
                    line.prepaid_is_paid = True
                else:
                    line.prepaid_is_paid = False
            elif move.supplier_invoice_ids:
                if all(
                    [
                        x.payment_state in ("paid", "reversed")
                        for x in move.supplier_invoice_ids
                    ]
                ):
                    line.prepaid_is_paid = True
                else:
                    line.prepaid_is_paid = False
            # OD to manage migration toward this system?
            else:
                line.prepaid_is_paid = True

    @api.depends(
        "timesheet_line_ids.discount", "timesheet_line_ids.unit_amount", "quantity"
    )
    def _compute_timesheet_qty(self):
        for record in self:
            record.timesheet_qty = (
                record.timesheet_line_ids._get_invoiceable_qty_with_unit(
                    record.product_uom_id
                )
            )
            if abs(record.timesheet_qty - record.quantity) > 0.001:
                record.timesheet_error = "⏰ %s" % record.timesheet_qty

    @api.depends(
        "move_id",
        "analytic_account_id.project_ids.partner_id",
        "move_id.move_type",
        "product_id.prepaid_revenue_account_id",
        "amount_currency",
    )
    def _compute_contribution_subtotal(self):
        for line in self:
            contribution_price = 0
            if (
                line.move_id.move_type in ["in_invoice", "in_refund"]
                and line.product_id.prepaid_revenue_account_id
                and line.analytic_account_id
            ):
                contribution = line.company_id.with_context(
                    partner=line.analytic_account_id.partner_id
                )._get_commission_rate()
                contribution_price = line.amount_currency / (1 - contribution)
            line.contribution_price_subtotal = contribution_price

    def open_task(self):
        self.ensure_one()
        action = self.env.ref("project.action_view_task").sudo().read()[0]
        action.update(
            {
                "res_id": self.task_id.id,
                "views": [x for x in action["views"] if x[1] == "form"],
            }
        )
        return action

    def _compute_account_id(self):
        res = super()._compute_account_id()
        product_lines = self.filtered(
            lambda line: line.display_type == "product"
            and line.move_id.is_invoice(True)
        )
        for line in product_lines:
            if (
                line.move_id.is_sale_document()
                and line.with_company(
                    line.company_id
                ).product_id.prepaid_revenue_account_id
            ):
                fiscal_position = line.move_id.fiscal_position_id
                accounts = line.with_company(
                    line.company_id
                ).product_id.product_tmpl_id.get_product_accounts(
                    fiscal_pos=fiscal_position
                )
                line.account_id = accounts["prepaid"] or line.account_id
        return res

    @api.constrains("account_id", "subcontractor_work_ids")
    def check_no_subcontractor_prepaid(self):
        for rec in self:
            if rec.account_id.is_prepaid_account and rec.subcontractor_work_ids:
                raise exceptions.UserError(
                    _(
                        "You can't have subcontractor on an invoice line with a prepaid"
                        " account."
                    )
                )
