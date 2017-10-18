# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models
import StringIO
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from collections import defaultdict
from openerp.tools.translate import _
from openerp.addons.account_move_base_import.parser.file_parser import (
    FileParser)
from openerp.tools import ustr

import logging
_logger = logging.getLogger(__name__)

try:
    import unicodecsv
except (ImportError, IOError) as err:
    _logger.debug(err)


def s2f(val):
    if len(val) == 0:
        return 0.0
    val = val.replace(',', '.')
    return float(val)


def format_date(date_str):
    """ Depending of the country the date may do not have the same format"""
    try:
        date = datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S %Z')
    except:
        date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S %Z')
    return date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)


class AmazonPaymentImporter(models.AbstractModel):
    _name = 'amazon.payment.importer'
    _description = 'Amazon Payment Importer'

    def _run(self, report, meta_attachment):
        _logger.info("Start to import bank Statement")

        backend = meta_attachment.amazon_backend_id
        # Create bank statement line for transferts
        backend.bank_journal_id.with_context(
            file_name=meta_attachment.name, backend=backend)\
            .multi_move_import(meta_attachment.datas, 'csv')


class AmazonFlatV2Parser(FileParser):

    def __init__(self, journal, ftype='csv', **kwargs):
        conversion_dict = {
            'label': ustr,
            'amount': float,
            }
        # set self.env for later ORM searches
        self.env = journal.env
        self.backend = self.env.context['backend']
        super(AmazonFlatV2Parser, self).__init__(
            journal, ftype=ftype,
            extra_fields=conversion_dict,
            **kwargs)

    @classmethod
    def parser_for(cls, parser_name):
        return parser_name == 'amazon_flat_v2'

    def _process_line(self, result, line):
        ttype = line['transaction-type']
        if ttype in ['Order', 'Refund']:
            order_ref = line['order-id']
            if line['amount-type'] in ('ItemPrice', 'Promotion'):
                result[ttype][order_ref]['amount'] += s2f(line['amount'])
            else:
                result[line['amount-description']] += s2f(line['amount'])
        else:
            result[line['amount-description']] += s2f(line['amount'])

    def _merge_line(self, lines):
        result = defaultdict(float)
        result.update({
            'Order': defaultdict(lambda: defaultdict(float)),
            'Refund': defaultdict(lambda: defaultdict(float)),
            })
        for line in lines:
            self._process_line(result, line)
        return result

    def _convert_parsed_to_row(self, parsed):
        res = []
        for key, vals in parsed.items():
            if key in ['Order', 'Refund']:
                for order_name, order_vals in vals.items():
                    res.append({
                        'label': '%s%s' % (
                            self.backend.sale_prefix, order_name),
                        'amount': order_vals['amount'],
                        'account_id': self.journal.receivable_account_id.id,
                        })
            else:
                res.append({
                    'label': key,
                    'amount': vals,
                    'account_id': self.journal.commission_account_id.id,
                    })
        return res

    def _parse(self, *args, **kwargs):
        self.result_row_list = []
        tmpfile = StringIO.StringIO()
        tmpfile.write(self.filebuffer)
        tmpfile.seek(0)

        reader = unicodecsv.DictReader(
            tmpfile, delimiter='\t', quoting=False,
            encoding='ISO-8859-15')

        first_line = reader.next()
        self.move_date = format_date(first_line['settlement-end-date'])
        self.period_id = self.env['account.period'].find(dt=self.move_date).id
        self.result_row_list.append({
            'label': _('Internal bank transfers'),
            'amount': -s2f(first_line['total-amount']),
            'account_id': self.journal.default_debit_account_id.id,
            'period_id': self.period_id,
            })
        result = self._merge_line(reader)
        self.result_row_list += self._convert_parsed_to_row(result)
        return True

    def get_move_line_vals(self, line, *args, **kwargs):
        amount = line.get('amount', 0.0)
        return {
            'name': line.get('label', '/'),
            'account_id': line['account_id'],
            'credit': amount > 0.0 and amount or 0.0,
            'debit': amount < 0.0 and -amount or 0.0,
            'period_id': self.period_id,
            'journal_id': self.journal.id,
        }
