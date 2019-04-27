# -*- coding: utf-8 -*-
# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    invoicing_stage_id = fields.Many2one(
        'project.task.type',
        'Invoicing Stage')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    invoicing = fields.Selection([
        ('progressive', 'Progressive'),
        ('none', 'None'),
        ('finished', 'Finished'),
        ], default='finished',
        )
