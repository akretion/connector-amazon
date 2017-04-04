# coding: utf-8
# Copyright 2017 Akretion (http://www.akretion.com).
# @author David BEAL <david.beal@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    external_origin = fields.Reference(selection='_authorised_models')

    @api.model
    def _authorised_models(self):
        """ Inherit this method to add more models depending of your
            modules dependencies
        """
        return [('amazon.backend', 'Amazon'),
                ('ir.attachment.metadata', 'Attachment Metadata')]
