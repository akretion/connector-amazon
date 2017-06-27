# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import _, api, fields, models
from openerp.exceptions import Warning as UserError


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

    @api.multi
    def populate_amazon_binding(self):
        # TODO make it complete lines instead of mass create ...
        # with a wizard/action from product list ?
        for rec in self:
            values = []
            if not rec.amazon_variant_bind_ids:
                backends = self.env['amazon.backend'].search([])
                for backend in backends:
                    values.extend(
                        [{'backend_id': backend.id, 'record_id': x.id}
                         for x in rec.product_variant_ids
                         if x.default_code])
                if not values:
                    raise UserError(
                        _("No backend or Reference for this product"))
                for vals in values:
                    self.env['amazon.product'].create(vals)
            else:
                raise UserError(_("Remove all items before to populate"))


class AmazonProduct(models.Model):
    _name = 'amazon.product'
    _inherits = {'product.product': 'record_id'}
    _description = 'Amazon Product'

    record_id = fields.Many2one(
        comodel_name='product.product', string='Product', required=True,
        ondelete='cascade')
    external_id = fields.Char(
        string='SKU',
        help="Code/SKU of the product in the marketplace "
             "(mandatory because of searching method in sales import")
    backend_id = fields.Many2one(
        comodel_name='amazon.backend', string='Backend', required=True)

    _sql_constraints = [
        ('external_id_uniq', 'unique(backend_id, external_id)',
         'A product can only have one external id by backend.'),
        ('product_backend_uniq', 'unique(backend_id, record_id)',
         'Couple product / backend must be unique.'),
    ]

    @api.multi
    @api.onchange('record_id')
    def onchange_product(self):
        for rec in self:
            rec.external_id = rec.record_id.default_code

    @api.model
    def create(self, vals):
        product = self.env['product.product'].browse(vals.get('record_id'))
        if not vals.get('external_id'):
            if product.default_code:
                vals['external_id'] = product.default_code
            else:
                raise UserError(
                    _("Missing SKU or product Reference with these data %s"
                      % vals))
        return super(AmazonProduct, self).create(vals)
