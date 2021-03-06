# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, _
import time
import datetime
from openerp.exceptions import Warning
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare


class travel(models.Model):

    """"""
    _name = 'logistic.travel'
    _description = 'travel'

    def _fnct_line_ordered(self):
        """"""
        res = {}
        # Por ahora no la usamos
        return res

    @api.model
    def _get_from_date(self):
        waybill_id = self._context.get('waybill_id', False)
        from_date = time.strftime('%Y-%m-%d %H:%M:%S')
        if waybill_id:
            travel_ids = self.search(
                [('waybill_id', '=', waybill_id)], order="id desc")
            if travel_ids:
                from_date = travel_ids[0].to_date
        return from_date

    def name_get(self, cr, uid, ids, context=None):
        # always return the full hierarchical name
        res = self._complete_name(
            cr, uid, ids, 'complete_name', None, context=context)
        return res.items()

    def _complete_name(self, cr, uid, ids, name, args, context=None):
        """ Forms complete name of location from parent location to child location.
        @return: Dictionary of values
        """
        res = {}
        for line in self.browse(cr, uid, ids):
            name = line.waybill_id.name or '' + ': '
            name += line.location_from_id.name
            name += ' - ' + line.location_to_id.name
            res[line.id] = name
        return res

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        ids = set()
        if name:
            ids.update(self.search(cr, user, args + [('location_from_id.name', operator, name)], limit=(
                limit and (limit - len(ids)) or False), context=context))
            if not limit or len(ids) < limit:
                ids.update(self.search(
                    cr, user, args + [('location_to_id.name', operator, name)], limit=limit, context=context))
            if not limit or len(ids) < limit:
                ids.update(self.search(
                    cr, user, args + [('waybill_id.name', operator, name)], limit=limit, context=context))
            ids = list(ids)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result

    @api.one
    @api.constrains('to_date', 'from_date')
    def _check_dates(self):
        if self.to_date and self.from_date:
            if self.from_date > self.to_date:
                raise Warning(
                    _('Error! From date must be lower then to date.'))

    from_date = fields.Datetime(
        string='From', required=True, default=_get_from_date)
    location_from_id = fields.Many2one(
        'logistic.location', string='Location From', required=True)
    to_date = fields.Datetime(string='To', required=True)
    location_to_id = fields.Many2one(
        'logistic.location', string='Location To', required=True)
    reference = fields.Char(string='Reference')
    partner_id = fields.Many2one(
        'res.partner', string='Customer', domain=[('customer', '=', True)])
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        context={'default_type': 'service',
                 'default_service_subtype': 'travel'},
        domain=[('type', '=', 'service'), ('service_subtype', '=', 'travel')])
    price = fields.Float(string='Price')
    invoice_line_id = fields.Many2one(
        'account.invoice.line', string='Invoice Line', readonly=True)
    waybill_id = fields.Many2one(
        'logistic.waybill',
        string='Waybill', required=True, ondelete='cascade')
    tractor_id = fields.Many2one(
        'fleet.vehicle',
        related='waybill_id.tractor_id',
        string='Tractor', readonly=True, store=True)
    ordered = fields.Boolean(
        compute='_fnct_line_ordered',
        arg=None,
        fnct_inv_arg=None, obj=None, string='Ordered?', readonly=True)
    driver_id = fields.Many2one(
        'res.partner',
        related='waybill_id.driver_id',
        string='Driver',
        domain=[('is_driver', '=', True)], readonly=True, store=True)
    invoice_id = fields.Many2one(
        'account.invoice',
        related='invoice_line_id.invoice_id',
        string=_('Invoice'),
        readonly=True
    )

    def on_change_location(self, cr, uid, ids, location_from_id, location_to_id, context=None):
        v = {}
        product_id = False
        if location_from_id and location_to_id:
            domain = [('type', '=', 'service'), ('service_subtype', '=', 'travel'), (
                'location_from_id', '=', location_from_id), ('location_to_id', '=', location_to_id)]
            # domain = [('type','=','service'),('service_subtype','=','travel'),
            #     '&',('location_from_id','=',location_from_id),('location_to_id','=',location_to_id),
            #     '&',('location_to_id','=',location_from_id),('location_from_id','=',location_to_id)]
            product_ids = self.pool.get('product.product').search(
                cr, uid, domain, context=context)
            if product_ids:
                product_id = product_ids[0]
        v['product_id'] = product_id
        return {'value': v}

    def on_change_from_date(self, cr, uid, ids, from_date, context=None):
        v = {}
        if from_date:
            from_date = (datetime.datetime.strptime(from_date, DEFAULT_SERVER_DATETIME_FORMAT) +
                         relativedelta(days=1)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            v['to_date'] = from_date
        else:
            v['to_date'] = False
        return {'value': v}

    @api.onchange('product_id', 'partner_id')
    def on_change_product(self):
        """"""
        price = False
        if self.product_id:
            self.location_from_id = self.product_id.location_from_id.id
            self.location_to_id = self.product_id.location_to_id.id
        if self.product_id and self.partner_id:
            if not self.partner_id.property_product_pricelist:
                pricelist_id = self.partner_id.property_product_pricelist
            else:
                pricelist_ids = self.env['product.pricelist'].search(
                    [('type', '=', 'sale')])
                if pricelist_ids:
                    pricelist_id = pricelist_ids[0]
                else:
                    raise Warning(
                        _('Error!'), _('There is no sale pricelist!'))
            date_order = time.strftime(DEFAULT_SERVER_DATE_FORMAT)
            price = pricelist_id.price_get(
                self.product_id.id, 1.0, self.partner_id.id, context={
                    'uom': self.product_id.uos_id,
                    'date': date_order,
                })[pricelist_id.id]
        self.price = price

    def action_invoice_create(self, cr, uid, ids, grouped=False, date_invoice=False, context=None):
        invoice_ids = []
        partner_currency = {}

        if context is None:
            context = {}
        # If date was specified, use it as date invoiced, usefull when invoices are generated this month and put the
        # last day of the last month as invoice date
        if date_invoice:
            context['date_invoice'] = date_invoice

        for o in self.browse(cr, uid, ids, context=context):
            pricelist = self.get_pricelist(
                cr, uid, o.partner_id, context=context)
            currency_id = pricelist.currency_id.id
            if not o.partner_id or not o.product_id:
                raise Warning(
                    _('Warning!'), _('To create invoice travels must have partner and product'))
            if (o.partner_id.id in partner_currency) and (partner_currency[o.partner_id.id] <> currency_id):
                raise Warning(
                    _('Error!'),
                    _('You cannot group travels having different currencies for the same partner.'))

            partner_currency[o.partner_id.id] = currency_id
        if grouped:
            for partner_id in partner_currency:
                travel_ids = self.search(
                    cr, uid, [('id', 'in', ids), ('partner_id', '=', partner_id)], context=context)
                invoice_ids.append(
                    self._invoice_create(cr, uid, travel_ids, context=context))
        else:
            for travel_id in ids:
                invoice_ids.append(
                    self._invoice_create(cr, uid, [travel_id], context=context))
        return invoice_ids

    def _invoice_create(self, cr, uid, ids, context=None):
        inv_obj = self.pool.get('account.invoice')
        if context is None:
            context = {}
        # TODO
        # self.check_travel_one_partner
        # Just to make clear that all ids should be from the same partner
        partner_travel_ids = ids
        invoice_line_ids = self.invoice_line_create(
            cr, uid, partner_travel_ids, context=context)

        invoice_vals = self._prepare_invoice(
            cr, uid, partner_travel_ids, invoice_line_ids, context=context)
        inv_id = inv_obj.create(cr, uid, invoice_vals, context=context)
        data = inv_obj.onchange_payment_term_date_invoice(cr, uid, [inv_id], invoice_vals[
                                                          'payment_term'], time.strftime(DEFAULT_SERVER_DATE_FORMAT))
        if data.get('value', False):
            inv_obj.write(cr, uid, [inv_id], data['value'], context=context)
        inv_obj.button_compute(cr, uid, [inv_id])
        return inv_id

    def get_pricelist(self, cr, uid, partner, context=None):
        if partner.property_product_pricelist:
            return partner.property_product_pricelist
        else:
            pricelist_ids = self.pool['product.pricelist'].search(
                cr, uid, [('type', '=', 'sale')], context=context)
            if pricelist_ids:
                pricelist_id = pricelist_ids[0]
            else:
                raise Warning(
                    _('Error!'), _('Order cannot be created because not sale pricelist exists!'))
        return self.pool['product.pricelist'].browse(cr, uid, pricelist_id, context=context)

    def invoice_line_create(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        create_ids = []
        if context.get('grouped_line'):
            product_ids = [x.product_id.id for x in self.browse(
                cr, uid, ids, context=context) if x.product_id]
            for product_id in list(set(product_ids)):
                travel_ids = self.search(
                    cr, uid, [('id', 'in', ids), ('product_id', '=', product_id)], context=context)
                travels = self.browse(cr, uid, travel_ids, context=context)
                vals = self._prepare_order_line_invoice_line(
                    cr, uid, travels, context=context)
                if vals:
                    inv_line_id = self.pool.get('account.invoice.line').create(
                        cr, uid, vals, context=context)
                    self.write(
                        cr, uid, travel_ids, {'invoice_line_id': inv_line_id}, context=context)
                    create_ids.append(inv_line_id)
        else:
            for travel in self.browse(cr, uid, ids, context=context):
                vals = self._prepare_order_line_invoice_line(
                    cr, uid, travel, context=context)
                if vals:
                    inv_line_id = self.pool.get('account.invoice.line').create(
                        cr, uid, vals, context=context)
                    self.write(
                        cr, uid, [travel.id], {'invoice_line_id': inv_line_id}, context=context)
                    create_ids.append(inv_line_id)
        return create_ids

    def _prepare_order_line_invoice_line(self, cr, uid, travel, context=None):
        """Prepare the dict of values to create the new invoice line for a
           sales order line. This method may be overridden to implement custom
           invoice generation (making sure to call super() to establish
           a clean extension chain).

           :param browse_record line: sale.order.line record to invoice
           :param int account_id: optional ID of a G/L account to force
               (this is used for returning products including service)
           :return: dict of values to create() the invoice line
        """
        res = {}
        if context.get('grouped_line'):
            if not travel[0].invoice_line_id:
                if travel[0].product_id:
                    account_id = travel[
                        0].product_id.property_account_income.id
                    if not account_id:
                        account_id = travel[
                            0].product_id.categ_id.property_account_income_categ.id
                    if not account_id:
                        raise Warning(_('Error!'),
                                      _('Please define income account for this product: "%s" (id:%d).') %
                                      (travel.product_id.name, travel.product_id.id,))
            fpos = travel[0].partner_id.property_account_position.id or False
            account_id = self.pool.get('account.fiscal.position').map_account(
                cr, uid, fpos, account_id)
            tax_ids = self.pool.get('account.fiscal.position').map_tax(
                cr, uid, fpos, travel[0].product_id.taxes_id)
            name = travel[0].product_id.name
            name += ', Hoja de Ruta: '
            name += ", ".join(
                [x.waybill_id.reference for x in travel if x.waybill_id.reference])
            refs = [x.reference for x in travel if x.reference]
            name += refs and ". Refs: " + ", ".join(refs) or ""
            pu = 0.0
            for travel_id in travel:
                uosqty = 1.0
                if uosqty:
                    pu = pu + round(travel_id.price,
                                    self.pool.get('decimal.precision').precision_get(cr, uid, 'Product Price'))
                if not account_id:
                    raise Warning(_('Error!'),
                                  _('There is no Fiscal Position defined or Income category account defined for default properties of Product categories.'))
            res = {
                'name': name,
                'account_id': account_id,
                'price_unit': pu,
                'quantity': uosqty,
                'uos_id': travel[0].product_id and travel[0].product_id.uom_id.id or False,
                'product_id': travel[0].product_id.id or False,
                'invoice_line_tax_id': [(6, 0, tax_ids)],
            }

        else:
            if not travel.invoice_line_id:
                if travel.product_id:
                    account_id = travel.product_id.property_account_income.id
                    if not account_id:
                        account_id = travel.product_id.categ_id.property_account_income_categ.id
                    if not account_id:
                        raise Warning(_('Error!'),
                                      _('Please define income account for this product: "%s" (id:%d).') %
                                      (travel.product_id.name, travel.product_id.id,))
                uosqty = self._get_line_qty(cr, uid, travel, context=context)
                uos_id = self._get_line_uom(cr, uid, travel, context=context)
                pu = 0.0
                if uosqty:
                    pu = round(travel.price,
                               self.pool.get('decimal.precision').precision_get(cr, uid, 'Product Price'))
                fpos = travel.partner_id.property_account_position.id or False
                account_id = self.pool.get('account.fiscal.position').map_account(
                    cr, uid, fpos, account_id)
                if not account_id:
                    raise Warning(_('Error!'),
                                  _('There is no Fiscal Position defined or Income category account defined for default properties of Product categories.'))
                tax_ids = self.pool.get('account.fiscal.position').map_tax(
                    cr, uid, fpos, travel.product_id.taxes_id)
                name = travel.product_id.name
                name += ', Hoja de Ruta: '
                name += travel.waybill_id.reference or ''
                name += travel.reference and '. Refs: ' + \
                    travel.reference or ''
                res = {
                    'name': name,
                    'account_id': account_id,
                    'price_unit': pu,
                    'quantity': uosqty,
                    # 'discount': line.discount,
                    'uos_id': uos_id,
                    'product_id': travel.product_id.id or False,
                    'invoice_line_tax_id': [(6, 0, tax_ids)],
                }

        return res

    def _get_line_qty(self, cr, uid, travel, context=None):

        return 1.0

    def _get_line_uom(self, cr, uid, travel, context=None):
        return travel.product_id and travel.product_id.uom_id.id or False

    def _prepare_invoice(self, cr, uid, partner_travel_ids, lines, context=None):
        """Prepare the dict of values to create the new invoice for a
           sales order. This method may be overridden to implement custom
           invoice generation (making sure to call super() to establish
           a clean extension chain).

           :param browse_record order: sale.order record to invoice
           :param list(int) line: list of invoice line IDs that must be
                                  attached to the invoice
           :return: dict of value to create() the invoice
        """
        travel = self.browse(cr, uid, partner_travel_ids[0], context=context)
        partner = travel.partner_id
        waybill = self.browse(
            cr, uid, partner_travel_ids[0], context=context).waybill_id
        company = waybill.company_id
        if context is None:
            context = {}
        journal_ids = self.pool.get('account.journal').search(cr, uid,
                                                              [('type', '=', 'sale'),
                                                               ('company_id', '=', company.id)],
                                                              limit=1)
        if not journal_ids:
            raise Warning(_('Error!'),
                          _('Please define sales journal for this company: "%s" (id:%d).') % (company.name, company.id))
        # Don know why but it does not take the translation
        # origin = _('Waybill')
        origin = _('Hoja de Ruta')
        invoice_vals = {
            'origin': origin,
            'type': 'out_invoice',
            'account_id': partner.property_account_receivable.id,
            'partner_id': partner.id,
            'journal_id': journal_ids[0],
            'invoice_line': [(6, 0, lines)],
            'currency_id': self.get_pricelist(cr, uid, partner, context=context).currency_id.id,
            'payment_term': partner.property_payment_term and partner.property_payment_term.id or False,
            'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
            'date_invoice': context.get('date_invoice', False),
            'company_id': company.id,
        }
        return invoice_vals
