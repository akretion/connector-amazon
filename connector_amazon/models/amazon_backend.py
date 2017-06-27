# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# @author David BEAL <david.beal@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import time

from openerp import _, api, fields, models
from openerp.exceptions import Warning as UserError

from .attachment import SUPPORTED_REPORT
import logging
_logger = logging.getLogger(__name__)

try:
    import iso8601
except ImportError:
    _logger.debug('Cannot `import iso8601` library.')

try:
    from boto.mws.connection import MWSConnection
    from boto.exception import BotoServerError
except ImportError:
    _logger.debug('Cannot `import boto` library.')


KEYCHAIN_HELP = "Data store by keychain (Settings > Configuration > Keychain)"
SECONDS_AFTER_EXCEPTION = 60


class AmazonBackend(models.Model):
    _name = 'amazon.backend'
    _inherit = ['keychain.backend', 'mail.thread']
    _backend_name = 'amazon'

    name = fields.Char(required=True)
    sale_prefix = fields.Char(
        string='Sale Prefix', track_visibility='onchange',
        help="Prefix applied in Sale Order (field 'name')")
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist', string='Pricelist',
        required=True, track_visibility='onchange',
        help="Pricelist used in imported sales")
    workflow_process_id = fields.Many2one(
        comodel_name='sale.workflow.process', string='Workflow',
        required=True, track_visibility='onchange',
        default=lambda self: self.env.ref(
            'sale_automatic_workflow.manual_validation'),
        help="Choose the right workflow: probably the manual one "
             "to check your data")
    accesskey = fields.Char(
        sparse="data", required=True, string="Access Key",
        help=KEYCHAIN_HELP)
    merchant = fields.Char(
        sparse="data", required=True, help=KEYCHAIN_HELP)
    marketplace = fields.Char(
        sparse="data", required=True, help=KEYCHAIN_HELP)
    shipping_product = fields.Many2one(
        comodel_name='product.product', string='Shipping Product',
        required=True, track_visibility='onchange',
        help="Choose an appropriate product (accounting settings) to store "
             "shipping fee")
    host = fields.Selection(
        selection=[
            ('mws.amazonservices.com', 'North America (NA)'),
            ('mws-eu.amazonservices.com', 'Europe (EU)'),
            ('mws.amazonservices.in', 'India (IN)'),
            ('mws.amazonservices.com.cn', 'China (CN)'),
            ('mws.amazonservices.jp', 'Japan (JP)'),
        ], required=True, track_visibility='onchange')
    encoding = fields.Selection(
        selection=[
            ('ISO-8859-15', 'ISO-8859-15'),
        ], required=True, track_visibility='onchange')
    import_report_from = fields.Datetime(
        string="Import From", required=True, default=fields.datetime.today(),
        help="Import sales to deliver from this date.")
    fba = fields.Boolean(
        string='Fulfillment By Amazon',
        help="Allow to access to Fulfillment by Amazon features.")
    import_fba_from = fields.Datetime(
        string="Import FBA From", required=True,
        default=fields.datetime.today(),
        help="Import Fulfillment by Amazon sales from this date.")
    fba_warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse', string='Warehouse',
        track_visibility='onchange',
        helper="Products are physically stored in an other location.\n"
               "Define a dedicated warehouse for this case")
    fba_workflow_process_id = fields.Many2one(
        comodel_name='sale.workflow.process', string='Workflow',
        required=True, track_visibility='onchange',
        default=lambda self: self.env.ref(
            'sale_automatic_workflow.manual_validation'),
        help="Choose the right workflow: for FBA, the best workflow "
             "is the automatic one \nbecause your sales "
             "are delivered and paid (default one is manual)")
    elapsed_time = fields.Selection(selection=[
        (2, '2 seconds'), (4, '4 seconds'), (6, '6 seconds')], default=4,
        help="Time elasped between 2 FBA sales imports:\n"
             "prevent to be throttled by Amazon")

    def _get_connection(self):
        self.ensure_one()
        account = self._get_existing_keychain()
        try:
            return MWSConnection(
                self.accesskey,
                account.get_password(),
                Merchant=self.merchant,
                host=self.host)
        except Exception as e:
            raise UserError(u"Amazon response:\n\n%s" % e)

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
            data = mws_api_call(
                mws, 'get_report', 'ReportId', report.ReportId,
                "Import Report '%s'")
            vals = self._prepare_attachment(report)
            vals['datas'] = base64.encodestring(data)
            self.env['ir.attachment.metadata'].create(vals)
            # Warning, we volontary commit here the report imported
            # this avoid useless re-importing it if the process failed
            self._cr.commit()

    @api.multi
    def import_report(self):
        for record in self:
            mws = record._get_connection()
            kwargs = {'ReportTypeList': SUPPORTED_REPORT.keys()}
            start = fields.Datetime.from_string(self.import_report_from)
            if start:
                # Be carefull Amazon documentation is outdated
                # the key for filtering the date is AvailableFromDate
                # and not RequestedFromDate
                kwargs['AvailableFromDate'] = start.isoformat()
            stop = None
            if mws:
                for response in mws.iter_call('GetReportList', **kwargs):
                    for report in response._result.ReportInfo:
                        self._import_report_id(mws, report)
                        stop = max(report.AvailableDate, stop)
                if not stop:
                    _logger.warning(
                        "There are no Amazon reports for the backend '%s'",
                        record.name)
                    continue
                record.import_report_from = iso8601.parse_date(stop)

    @api.multi
    def _create_sale(self, sale):
        """ We process sale order of the file
        """
        self.ensure_one()
        partner = self._get_customer(sale['partner'])
        part_ship = self._get_delivery_address(
            sale['part_ship'], sale['auto_insert']['origin'], partner)
        vals = {
            'name': (self.sale_prefix or '') + sale['auto_insert']['origin'],
            'partner_id': partner.id,
            'partner_shipping_id': part_ship.id,
            'pricelist_id': self.pricelist_id.id,
        }
        ship_price = self._prepare_products(sale['lines'])
        vals['order_line'] = [
            (0, 0, {key: val for key, val in line.items()
                    if key in self.env['sale.order.line']._fields.keys()})
            for line in sale['lines']
        ]
        if ship_price:
            ship_vals = {
                'product_uom_qty': 1,
                'price_unit': ship_price,
                'product_id': self.shipping_product.id,
            }
            vals['order_line'].append((0, 0, ship_vals), )
        if 'auto_insert' in sale:
            # used by these fields: date_order, origin, external_origin,
            # warehouse_id, ...
            for field in sale['auto_insert']:
                if field in self.env['sale.order']._fields:
                    vals[field] = sale['auto_insert'][field]
        return self.env['sale.order'].create(vals)

    def _get_customer(self, customer_data):
        partner_m = self.env['res.partner']
        partner = partner_m.search(
            [('email', '=', customer_data['email'])])
        if not partner:
            partner = partner_m.create(customer_data)
        return partner[0]

    def _get_delivery_address(self, part_ship, origin, partner):
        partner_m = self.env['res.partner']
        self._prepare_address(part_ship, origin)
        domain = [
            '|',
            ('active', '=', True),
            ('active', '=', False)]
        domain.extend([
            (fieldname, '=', val)
            for fieldname, val in part_ship.items()
            if fieldname in partner_m._fields])
        # we search identical partner active or not
        address = partner_m.search(domain)
        if not address:
            part_ship['parent_id'] = partner.id
            vals = {k: v for k, v in part_ship.items()
                    if k in partner_m._fields}
            address = partner_m.create(vals)
        return address[0]

    def _prepare_address(self, part_ship, origin):
        partner_m = self.env['res.partner']
        part_ship['country_id'], part_ship['state_id'] = \
            self._get_state_country(part_ship, origin)
        if part_ship.get('street3') and 'street3' not in partner_m._fields:
            # if street3 doesn't exist in odoo: according to modules
            part_ship['street2'] = '%s %s' % (
                part_ship['street2'], part_ship['street3'])

    def _prepare_products(self, lines):
        """ - check if product exists in amazon backend
            - gather shipping price
            return shipping_price
        """
        line_count, shipping_price = 0, 0
        products_in_exception = []
        for line in lines:
            shipping_line = float(line.get('shipping'))
            if shipping_line:
                shipping_price += shipping_line
            binding = self.env['amazon.product'].search(
                [('external_id', '=', line['sku']),
                 ('backend_id', '=', self.id)])
            if binding:
                lines[line_count]['product_id'] = binding[0].record_id.id
            else:
                self._worry_about_product_in_exception(
                    lines, products_in_exception, line_count)
            line_count += 1
        if products_in_exception:
            message = _(
                "No matching product with these sku '%s' in Amazon binding"
                % ', '.join(products_in_exception))
            self.message_post(body=message, subtype='mail.mt_comment')
            raise UserError(message)
        return shipping_price

    def _worry_about_product_in_exception(
            self, lines, products_in_exception, line_count):
        """ You may implement your own procedure """
        products_in_exception.append(lines[line_count]['sku'])

    def _get_state_country(self, part_ship, origin):
        """ country is mandatory, not state
        """
        country_code = part_ship.get('country')
        state_name = part_ship.get('state')
        country = self.env['res.country'].search([('code', '=', country_code)])
        if not country or not country_code:
            raise UserError(
                _("Unknow country code %s in sale %s ") % (
                    country_code, origin))
        state = False
        if state_name:
            state = self.env['res.country.state'].search(
                [('name', '=', state_name)])
            if not state:
                raise UserError(
                    _("Unknown state code %s in sale %s ") % (
                        state_name, origin))
        return(country.id, getattr(state, 'id', state))

    @api.multi
    def import_fba_delivered_sales(self):
        """ Import from Fulfillment by Amazon
        """
        for record in self:
            mws = record._get_connection()
            start = fields.Datetime.from_string(self.import_fba_from)
            try:
                sales = mws.list_orders(
                    CreatedAfter=start.isoformat(), OrderStatus=['Shipped'],
                    # marketplace must be in a list: weird Amazon !
                    MarketplaceId=[record.marketplace])
                _logger.info('%s FBA amazon sales will be imported',
                             len(sales.ListOrdersResult.Orders.Order))
                for order in sales.ListOrdersResult.Orders.Order:
                    _logger.debug(order)
                    data = self._extract_fba_sale(mws, order)
                    if self.env[('sale.order')].search([
                            ('origin', '=', data['auto_insert']['origin'])]):
                        continue
                    sale_date = data['auto_insert']['date_order']
                    self._create_sale(data)
                    record.import_fba_from = iso8601.parse_date(sale_date)
                    # We commit to avoid than a fail sale import
                    # prevent to save other valid sales
                    self._cr.commit()
                    # prevent to be throttled by Amazon
                    time.sleep(record.elapsed_time)
            except BotoServerError as bs:
                # pass
                message = _('Amazon BotoServerError %s %s %s') % (
                    bs.status, bs.reason, bs.body)
                raise UserError(message)
            except Exception as e:
                message = "Amazon exception '%s'" % e.message
                raise UserError(e.message)

    @api.multi
    def _extract_fba_sale(self, mws, order):
        self.ensure_one()
        sale = {
            'auto_insert': {
                'origin': order.AmazonOrderId,
                'date_order': order.PurchaseDate,
                'warehouse_id': self.fba_warehouse_id.id,
            },
            'partner': {
                'email': order.BuyerEmail,
                'name': order.BuyerName,
                'phone': False,
            },
            'part_ship': {
                'name': order.ShippingAddress.Name,
                'type': 'delivery',
                'phone': False,
                'street': getattr(
                    order.ShippingAddress, 'AddressLine1', False),
                'street2': getattr(
                    order.ShippingAddress, 'AddressLine2', False),
                'street3': getattr(
                    order.ShippingAddress, 'AddressLine3', False),
                'city': order.ShippingAddress.City,
                # Check which keys is submitted by amazon
                'state': getattr(order.ShippingAddress, 'State', False),
                'zip': order.ShippingAddress.PostalCode,
                'country': order.ShippingAddress.CountryCode,
            },
        }
        items = mws_api_call(
            mws, 'list_order_items', {'AmazonOrderId': order.AmazonOrderId},
            "Import Sale '%s'")
        lines = []
        for item in items.__dict__['ListOrderItemsResult'] \
                .OrderItems.OrderItem:
            _logger.debug(item)
            line = {
                'item': item.OrderItemId,
                'sku': item.SellerSKU,
                'name': '[%s] %s' % (item.SellerSKU, item.Title),
                'product_uom_qty': item.QuantityOrdered,
                # price is tax included, vat is computed in odoo
                'price_unit': extract_money(item.ItemPrice, self, item) + \
                extract_money(item.ItemTax),
                'shipping': extract_money(item.ShippingPrice) + \
                extract_money(item.ShippingTax),
            }
            lines.append(line)
        sale['lines'] = lines
        return sale

    @api.model
    def _extract_fba_sales(self):
        """ Triggered by cron """
        self.search([]).import_fba_delivered_sales()


def mws_api_call(mws, method, kwargs, message):
    """ called by:
        - mws.list_order_items(AmazonOrderId=order.AmazonOrderId)
        - mws.get_report(ReportId=report.ReportId)
    """
    try:
        data = getattr(mws, method)(**kwargs)
    except Exception as e:
        if hasattr(e, 'error_code'):
            if e.error_code == 'RequestThrottled':
                _logger.info(
                    "Request Throttled, please wait before auto retrying")
                time.sleep(SECONDS_AFTER_EXCEPTION)
                _logger.debug(message % kwargs[kwargs.keys[0]])
                data = getattr(mws, method)(kwargs)
            else:
                raise UserError(e)
        else:
            raise UserError(e)
    return data


def extract_money(field, backend=None, item=None):
    """ field is <class 'boto.mws.response.ComplexMoney'>
    """
    if field is None:
        return 0.0
    if backend:
        if field.__dict__['CurrencyCode'] != \
                backend.pricelist_id.currency_id.name:
            raise UserError(
                _("Currency '%(item_currency)s' used by SKU '%(sku)s' "
                  "is different than currency '%(pricelist_currency)s' "
                  "used by Pricelist of the backend '%(backend)s'.\n"
                  "Import in this case in not yet supported" %
                  {'item_currency': field.__dict__['CurrencyCode'],
                   'sku': item.SellerSKU,
                   'pricelist_currency': backend.pricelist_id.currency_id.name,
                   'backend': backend.name,
                   }))
    return float(field.__dict__['Amount'])
