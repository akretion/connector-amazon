# coding: utf-8
# Copyright 2017 Akretion (http://www.akretion.com).
# @author David BEAL <david.beal@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    amazon_backend_id = fields.Many2one(
        comodel_name='amazon.backend', string="Amazon Backend")
