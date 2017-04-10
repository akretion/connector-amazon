# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import StringIO
import logging

from openerp import _, models
from openerp.exceptions import Warning as UserError

_logger = logging.getLogger(__name__)

try:
    import unicodecsv
except (ImportError, IOError) as err:
    _logger.debug(err)


class AmazonSaleImporter(models.AbstractModel):
    _name = 'amazon.sale.importer'
    _description = 'Amazon Sale Importer'

    def _run(self, report, meta_attachment):
        """ Process the report and generate the sale order
        """
        file = StringIO.StringIO()
        file.write(report)
        file.seek(0)
        reader = unicodecsv.DictReader(
            file, fieldnames=self._get_header_fieldnames(),
            delimiter='\t', quoting=False,
            encoding=meta_attachment.amazon_backend_id.encoding)
        reader.next()  # we pass the file header
        sales = self._extract_infos(reader)
        file.close()
        backend = meta_attachment.amazon_backend_id
        for order_item, sale in sales.items():
            self._create_sale(sale, order_item, meta_attachment, backend)
        self._cr.commit()

    def _get_header_fieldnames(self):
        return [
            'order-id', 'order-item-id', 'purchase-date', 'payments-date',
            'buyer-email', 'buyer-name', 'buyer-phone-number', 'sku',
            'product-name', 'quantity-purchased', 'currency', 'item-price',
            'item-tax', 'shipping-price', 'shipping-tax',
            'ship-service-level', 'recipient-name', 'ship-address-1',
            'ship-address-2', 'ship-address-3', 'ship-city', 'ship-state',
            'ship-postal-code', 'ship-country', 'ship-phone-number',
            'delivery-start-date', 'delivery-end-date',
            'delivery-time-zone', 'delivery-Instructions', 'sales-channel',
        ]

    def _extract_infos(self, reader):
        sales = {}
        for line in reader:
            if not line.get('order-item-id'):
                continue
            if line['order-id'] in sales:
                sales[line['order-id']]['lines'].append(
                    self._get_sale_line(line))
            else:
                sales[line['order-id']] = {
                    'sale': {
                        'origin': line['order-id'],
                        'date_order': line['purchase-date'],
                    },
                    'partner': {
                        'email': line['buyer-email'],
                        'name': line['buyer-name'],
                        'phone': line['buyer-phone-number'],
                    },
                    'part_ship': {
                        'name': line['recipient-name'],
                        'type': 'delivery',
                        'phone': line['ship-phone-number'],
                        'street': line['ship-address-1'],
                        'street2': line['ship-address-2'],
                        'street3': line['ship-address-3'],
                        'city': line['ship-city'],
                        'state': line['ship-state'],
                        'zip': line['ship-postal-code'],
                        'country': line['ship-country'],
                    },
                    'lines': [self._get_sale_line(line)],
                }
        return sales

    def _get_sale_line(self, line):
        return {
            'item': line['order-item-id'],
            'sku': line['sku'],
            'name': '[%s] %s' % (line['sku'], line['product-name']),
            'product_uom_qty': line['quantity-purchased'],
            # price is in tax included, vat is computed in odoo
            'price_unit': float(line['item-price']) + float(line['item-tax']),
            'shipping': float(line['shipping-price']) + \
            float(line['shipping-tax']),
        }

    def _create_sale(self, sale, order_item, meta_attachment, backend):
        """ We process sale order of the file
        """
        partner = self._get_customer(sale['partner'])
        part_ship = self._get_delivery_address(
            sale['part_ship'], sale['sale']['origin'], partner)
        vals = {
            'name': backend.sale_prefix or '' + sale['sale']['origin'],
            'partner_id': partner.id,
            'partner_shipping_id': part_ship.id,
            'pricelist_id': backend.pricelist_id.id,
            'external_origin': 'ir.attachment.metadata,%s'
            % meta_attachment.id,
            'origin': sale['sale']['origin'],
        }
        ship_price = self._prepare_products(sale['lines'], backend)
        vals['order_line'] = [
            (0, 0, {key: val for key, val in line.items()})
            for line in sale['lines']]
        if ship_price:
            ship_vals = {
                'product_uom_qty': 1,
                'price_unit': ship_price,
                'product_id': backend.shipping_product.id,
            }
            vals['order_line'].append((0, 0, ship_vals), )
        self.env['sale.order'].create(vals)

    def _prepare_products(self, lines, backend):
        """ - check if product exist in amazon backend
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
                 ('backend_id', '=', backend.id)])
            if binding:
                lines[line_count]['product_id'] = binding[0].record_id.id
            else:
                products_in_exception.append(line['sku'])
            line_count += 1
        if products_in_exception:
            raise UserError(
                _("No matching product with these sku '%s' in Amazon binding"
                  % ', '.join(products_in_exception)))
        return shipping_price

    def _get_customer(self, customer_data):
        partner_m = self.env['res.partner']
        partner = partner_m.search(
            [('email', '=', customer_data['email'])])
        if not partner:
            partner = partner_m.create(customer_data['partner'])
        return partner[0]

    def _get_delivery_address(self, part_ship, origin, partner):
        partner_m = self.env['res.partner']
        self._prepare_address(part_ship, origin)
        address = partner_m.search([
            (fieldname, '=', val)
            for fieldname, val in part_ship.items()
            if fieldname in partner_m._fields])
        if not address:
            part_ship['parent_id'] = partner.id
            vals = {k: v for k, v in part_ship.items()
                    if k in partner_m._fields}
            partner = partner_m.create(vals)
        return address[0]

    def _prepare_address(self, part_ship, origin):
        partner_m = self.env['res.partner']
        part_ship['country_id'], part_ship['state_id'] = \
            self._get_state_country(part_ship, origin)
        if part_ship.get('street3') and 'street3' not in partner_m._fields:
            # if street3 doesn't exist in odoo: according to modules
            part_ship['street2'] = '%s %s' % (
                part_ship['street2'], part_ship['street3'])

    def _get_state_country(self, part_ship, origin):
        """ country is mandatory, not state
        """
        country = self.env['res.country'].search(
            [('code', '=', part_ship.get('country'))])
        if not country or not part_ship.get('country'):
            raise UserError(
                _("Unknow country code %s in sale %s " % (
                    part_ship.get('code'), origin)))
        state = False
        if part_ship.get('state'):
            state = self.env['res.country.state'].search(
                [('code', '=', part_ship.get('state'))])
            if not state:
                raise UserError(
                    _("Unknown state code %s in sale %s " % (
                        part_ship.get('state'), origin)))
        return(country.id, getattr(state, 'id', state))
