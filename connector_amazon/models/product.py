# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    amazon_bind_ids = fields.One2many(
        'amazon.product',
        'record_id',
        'Amazon Binding')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    amazon_variant_bind_ids = fields.One2many(
        'amazon.product',
        'product_tmpl_id',
        'Amazon Binding')


class AmazonProduct(models.Model):
    _name = 'amazon.product'
    _inherits = {'product.product': 'record_id'}
    _description = 'Amazon Product'

    record_id = fields.Many2one(
        'product.product',
        'Product')
    external_id = fields.Char(required=True)
    backend_id = fields.Many2one(
        'amazon.backend',
        'Backend',
        required=True)

    _sql_constraints = [
        ('external_id_uniq', 'unique(backend_id, external_id)',
         'A product can only have one external id by backend.'),
        ]
