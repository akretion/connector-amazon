# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Connector Amazon",
    "summary": "Connector for selling on Amazon Marketplace",
    "version": "8.0.1.0.1",
    "category": "Sales",
    "website": "www.akretion.com",
    "author": " Akretion",
    "license": "AGPL-3",
    "installable": True,
    "external_dependencies": {
        "python": [
            'boto',
            'iso8601',
            'unicodecsv',
        ],
        "bin": [],
    },
    "depends": [
        # Dependency on connector are just here for a better usability
        # Maybe we will remove it in the futur if it's problematic
        "connector_base_product",
        "sale_automatic_workflow",
        "base_sparse_field",
        "keychain",
        "attachment_base_synchronize",
        "web_m2x_options",
    ],
    "data": [
        "views/amazon_backend_view.xml",
        "views/product_view.xml",
        "views/partner_view.xml",
        "views/sale_view.xml",
        "views/metadata_view.xml",
        "data/data.xml",
        "security/ir.model.access.csv",
    ],
    "demo": [
        'demo/demo.xml',
        'demo/amazon.product.csv',
    ],
    "qweb": [
    ]
}
