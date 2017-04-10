# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models
import base64

SUPPORTED_REPORT = {
    '_GET_FLAT_FILE_ORDERS_DATA_': 'Amazon Order',
    '_GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2_': 'Amazon Bank Statement',
}


class IrAttachmentMetadata(models.Model):
    _inherit = 'ir.attachment.metadata'

    amazon_backend_id = fields.Many2one(
        comodel_name='amazon.backend', string='Amazon Backend')
    amazon_report_id = fields.Char(string="Amazon Report")
    file_type = fields.Selection(selection_add=SUPPORTED_REPORT.items())

    _sql_constraints = [
        ('uniq_report_per_backend',
         'unique(amazon_backend_id, amazon_report_id)',
         'Amazon Report must be uniq per backend')]

    def _run(self):
        report = base64.b64decode(self.datas)
        if self.file_type == '_GET_FLAT_FILE_ORDERS_DATA_':
            self.env['amazon.sale.importer']._run(report, self)
        elif self.file_type == '_GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2_':
            self.env['amazon.payment.importer']._run(report, self)
