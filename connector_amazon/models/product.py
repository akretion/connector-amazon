# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    amazon_bind_ids = fields.One2many(
        comodel_name='amazon.product',
        inverse_name='record_id',
        string='Amazon Binding')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    amazon_variant_bind_ids = fields.One2many(
        comodel_name='amazon.product',
        inverse_name='product_tmpl_id',
        string='Amazon Binding')


class AmazonProduct(models.Model):
    _name = 'amazon.product'
    _inherits = {'product.product': 'record_id'}
    _description = 'Amazon Product'

    record_id = fields.Many2one(
        comodel_name='product.product', string='Product', required=True,
        ondelete='cascade')
    external_id = fields.Char(
        string='SKU',
        help="Code/sku of the product in the marketplace")
    backend_id = fields.Many2one(
        comodel_name='amazon.backend', string='Backend', required=True)

    _sql_constraints = [
        ('external_id_uniq', 'unique(backend_id, external_id)',
         'A product can only have one external id by backend.'),
    ]

    @api.multi
    @api.onchange('record_id')
    def onchange_product(self):
        for rec in self:
            rec.external_id = rec.record_id.default_code
