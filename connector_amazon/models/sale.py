# coding: utf-8
# Copyright 2017 Akretion (http://www.akretion.com).
# @author David BEAL <david.beal@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    external_origin = fields.Reference(selection='_authorised_models')
    amazon_backend_id = fields.Many2one(
        'amazon.backend',
        'Amazon Backend')
    is_amazon_fba = fields.Boolean()

    @api.model
    def _prepare_invoice(self, order, lines):
        res = super(SaleOrder, self)._prepare_invoice(order, lines)
        if order.amazon_backend_id:
            backend = order.amazon_backend_id
            if order.is_amazon_fba:
                if backend.fba_sale_journal_id:
                    res['journal_id'] = backend.fba_sale_journal_id.id
                if backend.fba_receivable_account_id:
                    res['account_id'] = backend.fba_receivable_account_id.id
            else:
                if backend.sale_journal_id:
                    res['journal_id'] = backend.sale_journal_id.id
                if backend.receivable_account_id:
                    res['account_id'] = backend.receivable_account_id.id
        return res

    @api.model
    def _authorised_models(self):
        """ Inherit this method to add more models depending of your
            modules dependencies
        """
        return [('ir.attachment.metadata', 'Attachment Metadata')]
