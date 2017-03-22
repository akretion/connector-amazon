# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from openerp import api, fields, models
from boto.mws.connection import MWSConnection
from openerp.tools.config import config


class AmazonBackend(models.Model):
    _name = 'amazon.backend'
    _inherit = 'keychain.backend'
    _backend_name = 'amazon'

    name = fields.Char()
    accesskey = fields.Char(
        sparse="data",
        required=True,
        string="Access Key")
    merchant = fields.Char(
        sparse="data",
        required=True)
    marketplace = fields.Char(
        sparse="data",
        required=True)
    uri = fields.Char(
        sparse="data",
        required=True)
