# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import StringIO
import unicodecsv

from openerp import _, models
from openerp.exceptions import Warning as UserError


class AmazonSaleImporter(models.AbstractModel):
    _name = 'amazon.sale.importer'
    _description = 'Amazon Sale Importer'

    def _run(self, report, meta_attachment):
        """ Process the report and generate the sale order
        """
        fieldnames = [
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
        file = StringIO.StringIO()
        file.write(report)
        file.seek(0)
        reader = unicodecsv.DictReader(
            file, fieldnames=fieldnames, delimiter='\t', quoting=False,
            encoding=meta_attachment.amazon_backend_id.encoding)
        reader.next()  # we pass the file header
        sales = self._extract_infos(reader)
        file.close()
        return self._create_sales(sales, meta_attachment)

    def _extract_infos(self, reader):
        sales = {}

        def reset_empty(value):
            if value == '':
                return False
            return value

        for line in reader:
            if not line.get('order-item-id'):
                continue
            if line['order-id'] in sales:
                vals = sales[line['order-id']]
                vals['lines'].append(self._add_sale_line(line))
            else:
                vals = {
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
                        'phone': reset_empty(line['ship-phone-number']),
                        # TODO use with split address
                        'street': reset_empty(line['ship-address-1']),
                        'street2': reset_empty(line['ship-address-2']),
                        'street3': reset_empty(line['ship-address-3']),
                        'city': line['ship-city'],
                        'state': reset_empty(line['ship-state']),
                        'zip': reset_empty(line['ship-postal-code']),
                        'country': line['ship-country'],
                    },
                    'lines': [self._add_sale_line(line)],
                }
            sales[line['order-id']] = vals
        return sales

    def _add_sale_line(self, line):
        return {
            'item': line['order-item-id'],
            'default_code': line['sku'],
            'name': line['product-name'],
            'quantity': line['quantity-purchased'],
            'price': line['item-price'],
            'tax': line['item-tax'],
            'port': line['shipping-price'],
            'instruction': line['delivery-Instructions'],
        }

    def _create_sales(self, sales, meta_attach):
        """ We process all sale orders of the file
        """
        for order_item, sale in sales.items():
            partner, part_ship = self._get_partners(sale)
            vals = {
                'name': '%s %s' % (
                    meta_attach.amazon_backend_id.sale_prefix or '',
                    sale['sale']['origin']),
                'partner_id': partner.id,
                'partner_shipping_id': part_ship.id,
                'pricelist_id': meta_attach.amazon_backend_id.pricelist_id.id,
                'external_origin': 'ir.attachment.metadata,%s'
                % meta_attach.id,
                'origin': sale['sale']['origin'],
            }
            if sale.get('lines'):
                self._complete_products(sale['lines'])
                vals['order_line'] = [
                    (0, _, {key: val for key, val in line.items()})
                    for line in sale['lines']]
            self.env['sale.order'].create(vals)

    def _get_partners(self, sale):
        """ We have to search or create partners: main and shipping partner
        """
        partner_m = self.env['res.partner']
        partner = partner_m.search(
            [('email', '=', sale['partner']['email'])])
        part_ship = False
        if partner:
            part_ship = self._search_shipping_partner(sale, partner_m)
        else:
            partner = partner_m.create(sale['partner'])
        if not part_ship:
            sale['part_ship']['parent_id'] = partner.id
            vals = {k: v for k, v in sale['part_ship'].items()
                    if k in partner_m._fields}
            part_ship = partner_m.create(vals)
        return (partner[0], part_ship[0])

    def _search_shipping_partner(self, sale, partner_m):
        ship = sale['part_ship']
        sale['part_ship']['country_id'], sale['part_ship']['state_id'] = \
            self._get_state_country(sale)
        domain = [
            (fieldname, '=', val)
            for fieldname, val in ship.items()
            if fieldname in partner_m._fields]
        return partner_m.search(domain)

    def _complete_products(self, lines):
        count_line = 0
        products_in_exception = []
        for line in lines:
            product = self.env['product.product'].search(
                [('default_code', '=', line['default_code'])])
            if product:
                lines[count_line]['product_id'] = product.id
            else:
                products_in_exception.append(line['default_code'])
            count_line += 1
        if products_in_exception:
            raise UserError(
                _("No matching product with these sku/default_code '%s'"
                  % products_in_exception))

    def _get_state_country(self, sale):
        """ country is mandatory, not state
        """
        country = self.env['res.country'].search(
            [('code', '=', sale['part_ship'].get('country'))])
        if not country or not sale['part_ship'].get('country'):
            raise UserError(
                _("Unknow country code %s in sale %s " % (
                    sale['part_ship'].get('code'),
                    sale['sale']['origin'])))
        state = False
        if sale['part_ship'].get('state'):
            state = self.env['res.country.state'].search(
                [('code', '=', sale['part_ship'].get('state'))])
            if not state:
                raise UserError(
                    _("Unknown state code %s in sale %s " % (
                        sale['part_ship'].get('state'),
                        sale['sale']['origin'])))
        return(country.id, getattr(state, 'id', state))
