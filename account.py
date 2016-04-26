# This file is part of the nodux_account_invoice_multisequence module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, In, Not
from trytond.transaction import Transaction


__all__ = ['AccountJournalInvoiceSequence', 'Journal', 'FiscalYear', 'Invoice']
__metaclass__ = PoolMeta

STATES = {
    'readonly': ~Eval('active'),
}

DEPENDS = ['active']


class AccountJournalInvoiceSequence(ModelSQL, ModelView):
    'Account Journal Invoice Sequence'
    __name__ = 'account.journal.invoice.sequence'
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscalyear',
        required=True, domain=[
            ('company', '=', Eval('company', -1)),
            ], depends=['company'])
    period = fields.Many2One('account.period', 'Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear'))
            ], depends=['fiscalyear'])
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True)
    type = fields.Function(fields.Char('Type'), 'on_change_with_type')
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence',
        states={
            'required': Eval('type') == 'revenue',
            'invisible': Eval('type') != 'revenue',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Credit Note Sequence',
        states={
            'required': Eval('type') == 'revenue',
            'invisible': Eval('type') != 'revenue',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence',
        states={
            'required': Eval('type') == 'expense',
            'invisible': Eval('type') != 'expense',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence',
        states={
            'required': Eval('type') == 'expense',
            'invisible': Eval('type') != 'expense',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])
        
    
    users = fields.Many2One('sale.device', 'Puntos de Venta', required=True)

    
    @classmethod
    def __setup__(cls):
        super(AccountJournalInvoiceSequence, cls).__setup__()
        cls._sql_constraints += [
            ('period_uniq', 'UNIQUE(journal, period)',
                'Period can be used only once per Journal Sequence.'),
        ]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('journal')
    def on_change_with_type(self, name=None):
        if self.journal:
            return self.journal.type

    """
    @staticmethod
    def default_journal():
        pool = Pool()
        Journal = pool.get('account.journal')
        journal = Journal.search([('type' ,'=', 'expense')])
        print "Libro" ,journal
        for j in journal:
            journal_d = j
        return journal_d
    """
        
class Journal:
    __name__ = 'account.journal'
    sequences = fields.One2Many('account.journal.invoice.sequence', 'journal',
        'Sequences', states={
            'invisible': Not(In(Eval('type'), ['revenue', 'expense'])),
            })

    def get_invoice_sequence(self, invoice):
        pool = Pool()
        Date = pool.get('ir.date')
        date = invoice.invoice_date or Date.today()
        for sequence in self.sequences:
            period = sequence.period
            if period and (period.start_date <= date and
                    period.end_date >= date):
                return getattr(sequence, invoice.type + '_sequence')
        for sequence in self.sequences:
            fiscalyear = sequence.fiscalyear
            if (fiscalyear.start_date <= date and
                    fiscalyear.end_date >= date):
                return getattr(sequence, invoice.type + '_sequence')

class FiscalYear:
    __name__ = 'account.fiscalyear'
    journal_sequences = fields.One2Many('account.journal.invoice.sequence',
        'fiscalyear', 'Secuencia de comprobantes por punto de venta')

class Invoice:
    __name__ = 'account.invoice'

    def set_number(self):
        '''
        Set number to the invoice
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        User = pool.get('res.user')
        user = User.search([('id', '=', self.create_uid.id)])
        Period = pool.get('account.period')
        test_state = True
        
        shop = Transaction().context.get('shop')
        
        if self.type in ('in_invoice', 'in_credit_note'):
            test_state = False
             
        if user:
            for u in user:
                punto_emision = u.sale_device
        else:
            punto_emision = shop 
               
        Sequence = pool.get('ir.sequence.strict')
        Sequences = pool.get('account.journal.invoice.sequence')
        sequence1 = Sequences.search([('users','=', punto_emision)])
        type_c = self.type
        
        if sequence1:
            for s in sequence1:
                if type_c == 'out_invoice':
                    sequence = s.out_invoice_sequence
                if type_c == 'in_invoice':
                    sequence = s.in_invoice_sequence
                if type_c == 'in_credit_note':
                    sequence = s.in_credit_note_sequence
                if type_c == 'out_credit_note':
                    sequence = s.out_credit_note_sequence
        else:
            accounting_date = self.accounting_date or self.invoice_date
            period_id = Period.find(self.company.id,
                date=accounting_date, test_state=test_state)
            period = Period(period_id)
            sequence = period.get_invoice_sequence(self.type)
        
        if sequence:
            with Transaction().set_context(
                    date=self.invoice_date or Date.today()):
                self.number = Sequence.get_id(sequence.id)
                if (not self.invoice_date
                        and self.type in ('out_invoice', 'out_credit_note')):
                    self.invoice_date = Transaction().context['date']
                self.save()
        print self.number
        return super(Invoice, self).set_number()
