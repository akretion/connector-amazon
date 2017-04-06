# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import time

from openerp import api, fields, models
from openerp.exceptions import Warning as UserError

from .attachment import REPORT_SUPPORTED
import logging
_logger = logging.getLogger(__name__)

try:
    import iso8601
except ImportError:
    _logger.debug('Cannot `import iso8601` library.')

try:
    from boto.mws.connection import MWSConnection
except ImportError:
    _logger.debug('Cannot `import boto` library.')


class AmazonBackend(models.Model):
    _name = 'amazon.backend'
    _inherit = 'keychain.backend'
    _backend_name = 'amazon'
    _report_per_page = 50

    name = fields.Char()
    sale_prefix = fields.Char(
        string='Sale Prefix',
        help="Prefix applied in Sale Order (field 'name')")
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist', string='Pricelist', required=True)
    workflow_process_id = fields.Many2one(
        comodel_name='sale.workflow.process', string='Worflow', required=True)
    accesskey = fields.Char(
        sparse="data", required=True, string="Access Key")
    merchant = fields.Char(
        sparse="data", required=True)
    marketplace = fields.Char(
        sparse="data", required=True)
    shipping_product = fields.Many2one(
        comodel_name='product.product', string='Shipping Product',
        required=True)
    host = fields.Selection(
        selection=[
            ('mws.amazonservices.com', 'North America (NA)'),
            ('mws-eu.amazonservices.com', 'Europe (EU)'),
            ('mws.amazonservices.in', 'India (IN)'),
            ('mws.amazonservices.com.cn', 'China (CN)'),
            ('mws.amazonservices.jp', 'Japan (JP)'),
        ], required=True)
    encoding = fields.Selection(
        selection=[
            ('ISO-8859-15', 'ISO-8859-15'),
            ('UTF-8', 'UTF-8'),
        ], required=True)
    import_report_from = fields.Datetime(string="Import From")

    def _get_connection(self):
        self.ensure_one()
        account = self._get_existing_keychain()
        return MWSConnection(
            self.accesskey,
            account.get_password(),
            Merchant=self.merchant,
            host=self.host)

    def _prepare_attachment(self, report):
        return {
            'name': report.ReportId,
            'amazon_report_id': report.ReportId,
            'datas_fname': report.ReportId + ".csv",
            'state': 'pending',
            'sync_date': iso8601.parse_date(report.AvailableDate),
            'file_type': report.ReportType,
            'amazon_backend_id': self.id,
        }

    @api.multi
    def _import_report_id(self, mws, report):
        # TODO check if report already exist
        attch_obj = self.env['ir.attachment.metadata']
        if attch_obj.search([
                ('amazon_backend_id', '=', self.id),
                ('name', '=', report.ReportId)]):
            _logger.debug("Report %s already exist, skip it" % report.ReportId)
        else:
            _logger.debug("Import Report %s" % report.ReportId)
            try:
                data = mws.get_report(ReportId=report.ReportId)
            except Exception, e:
                if e.error_code == 'RequestThrottled':
                    _logger.info(
                        "Request Throttled, please wait before auto retrying")
                    time.sleep(60)
                    _logger.debug("Import Report %s" % report.ReportId)
                    data = mws.get_report(ReportId=report.ReportId)
                else:
                    raise
            vals = self._prepare_attachment(report)
            vals['datas'] = base64.encodestring(data)
            self.env['ir.attachment.metadata'].create(vals)
            # Warning, we volontary commit here the report imported
            # this avoid useless re-importing it if the process failed
            self._cr.commit()

    @api.multi
    def import_report(self):
        for record in self:
            try:
                mws = record._get_connection()
                kwargs = {'ReportTypeList': REPORT_SUPPORTED.keys()}
                start = fields.Datetime.from_string(self.import_report_from)
                if start:
                    # Be carefull Amazon documentation is outdated
                    # the key for filtering the date is AvailableFromDate
                    # and not RequestedFromDate
                    kwargs['AvailableFromDate'] = start.isoformat()
                stop = None
                for response in mws.iter_call('GetReportList', **kwargs):
                    for report in response._result.ReportInfo:
                        self._import_report_id(mws, report)
                        stop = max(report.AvailableDate, stop)
                record.import_report_from = iso8601.parse_date(stop)
            except Exception as e:
                raise UserError(u"Amazon response:\n\n%s" % e)
