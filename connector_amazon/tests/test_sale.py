# coding: utf-8
# © 2017 David BEAL @ Akretion

from openerp.tests.common import TransactionCase
from openerp import api


class AmazonSale(TransactionCase):

    def setUp(self):
        super(AmazonSale, self).setUp()
        # We define a specific environment to escape commit
        # https://github.com/odoo/odoo/blob/9.0/openerp/tests/common.py#L245
        self.registry.enter_test_mode()
        self.env = api.Environment(
            self.registry.test_cr, self.env.uid, self.env.context)

    def test_import_file_fail(self):
        attachm = self.env.ref('connector_amazon.amazon_sale_demo3')
        attachm.run()
        self.assertTrue(attachm.state_message)
        self.assertEqual(attachm.state_message[:24],
                         "No matching product with")

    def test_import_file_ok(self):
        attachm = self.env.ref('connector_amazon.amazon_sale_demo')
        attachm.run()
        self.assertEqual(attachm.state_message, False)

    def test_mass_import_sales(self):
        attachm = self.env.ref('connector_amazon.amazon_sale_demo2')
        attachm.run()
        reference = 'ir.attachment.metadata,%s' % attachm.id
        sales = self.env['sale.order'].search(
            [('external_origin', '=', reference)])
        self.assertEqual(len(sales), 10)

    def tearDown(self):
        # We leave specific environment
        self.registry.leave_test_mode()
        super(AmazonSale, self).tearDown()
