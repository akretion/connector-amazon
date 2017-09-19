# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    import_type = fields.Selection(
        selection_add=[('amazon_flat_v2', 'Amazon Flat V2')])
