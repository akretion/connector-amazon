# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# @author David BEAL <david.beal@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import StringIO
import logging

from openerp import models

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
        backend = meta_attachment.amazon_backend_id
        file = StringIO.StringIO()
        file.write(report)
        file.seek(0)
        reader = unicodecsv.DictReader(
            file, fieldnames=self._get_header_fieldnames(),
            delimiter='\t', quoting=False,
            encoding=backend.encoding)
        reader.next()  # we pass the file header
        sales = self._extract_infos(reader)
        file.close()
        for item in sales:
            sale = sales[item]
            sale['auto_insert'].update({
                'external_origin': 'ir.attachment.metadata,%s'
                % meta_attachment.id,
                'workflow_process_id': backend.workflow_process_id.id,
            })
            if backend._should_skip_sale_order(
                    sale['auto_insert']['origin'], is_fba=False):
                _logger.debug(
                    "Order %s already have been imported, skip it",
                    sale['auto_insert']['origin'])
                continue
            backend._create_sale(sales[item])

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
                    'auto_insert': {
                        # these values will be inserted
                        # if matching field exists in the ERP
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
            # price is tax included, vat is computed in odoo
            'price_unit':
                (float(line['item-price']) + float(line['item-tax']))\
                / float(line['quantity-purchased']),
            'shipping': float(line['shipping-price']) + \
            float(line['shipping-tax']),
            'discount': 0,
        }
