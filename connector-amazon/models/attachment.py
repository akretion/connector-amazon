# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, fields, models


class IrAttachmentMetadata(models.Model):
    _inherit = 'ir.attachment.metadata'

    amazon_backend_id = fields.Many2one(
        'amazon.backend',
        'Amazon Backend')
    amazon_report_id = fields.Char()
    file_type = fields.Selection(selection_add=[
        ('_GET_FLAT_FILE_ORDERS_DATA_', 'Amazon Order'),
        ('_GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2_',
            'Amazon Bank Statement')
        ])

    _sql_constraints = [
        ('uniq_report_per_backend',
         'uniq(amazon_backend_id, amazon_report_id)',
         'Amazon Report must be uniq per backend')]
