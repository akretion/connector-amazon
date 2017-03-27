# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from openerp import models


class AmazonSaleImporter(models.AbstractModel):
    _name = 'amazon.sale.importer'
    _description = 'Amazon Sale Importer'

    def _run(self, report):
        # TODO process the report and generate the sale order
        pass
