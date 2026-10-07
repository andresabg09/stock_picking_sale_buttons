from datetime import date

from odoo import http
from odoo.http import request
from odoo.osv import expression


class DkhCheckout(http.Controller):
    """Confirmación del pedido de la tienda (Versión H).

    "Confirmar pedido" guarda Forma de Pago, Fecha especial e ITBMS en la COTIZACIÓN y la deja
    lista para que el equipo la confirme (no se confirma sola). Exige el pedido mínimo."""

    @http.route('/shop/dk/confirmar', type='http', auth='user', website=True, methods=['POST'], sitemap=False)
    def confirm(self, payment_method='', special_date='', itbms=None, **kw):
        order = request.website.sale_get_order()
        if not order or not order.website_order_line or order.state != 'draft':
            return request.redirect('/shop/cart')
        if order._dkh_min_missing() > 0:
            return request.redirect('/shop/cart?dkh_err=min')
        valid = dict(order._fields['custom_payment_method']._description_selection(request.env))
        if payment_method not in valid:
            return request.redirect('/shop/cart?dkh_err=pay')
        vals = {
            'custom_payment_method': payment_method,
            'custom_itbms_required': bool(itbms),
            'custom_special_delivery_date': False,
        }
        if special_date:
            try:
                chosen = date.fromisoformat(special_date)
                if chosen >= date.today():
                    vals['custom_special_delivery_date'] = chosen
            except ValueError:
                pass
        order = order.sudo()
        order.write(vals)
        order.message_post(body='Pedido enviado desde la tienda. Forma de pago: %s%s%s.' % (
            valid[payment_method],
            ' · ITBMS: sí' if itbms else ' · ITBMS: no',
            (' · Entrega especial: %s' % vals['custom_special_delivery_date']) if vals['custom_special_delivery_date'] else '',
        ))
        request.session['dkh_last_order_id'] = order.id
        request.session['sale_order_id'] = None
        request.session['website_sale_cart_quantity'] = 0
        return request.redirect('/shop/dk/gracias')

    @http.route('/shop/dk/gracias', type='http', auth='user', website=True, sitemap=False)
    def thanks(self, **kw):
        order_id = request.session.get('dkh_last_order_id')
        order = request.env['sale.order'].sudo().browse(order_id).exists() if order_id else request.env['sale.order']
        if order and order.partner_id.commercial_partner_id != request.env.user.partner_id.commercial_partner_id:
            order = request.env['sale.order']
        return request.render('stock_picking_sale_buttons.dkh_thanks', {'order': order})

    @http.route('/shop/dk/scan', type='json', auth='public', website=True, sitemap=False)
    def scan(self, code='', **kw):
        """El escáner de la cámara: un código de barras = ese producto en el pedido."""
        code = (code or '').strip()
        if not code:
            return {'found': False}
        Template = request.env['product.template']
        domain = expression.AND([request.website.sale_product_domain(), [
            '|', '|',
            ('product_variant_ids.barcode', '=', code),
            ('product_variant_ids.barcode_ids.name', '=', code),
            ('default_code', '=', code),
        ]])
        found = Template.search(domain, limit=2)
        if len(found) != 1 or found.product_variant_count != 1:
            return {'found': False, 'many': len(found) > 1, 'url': '/shop?search=%s' % code}
        product = found.product_variant_id
        order = request.website.sale_get_order(force_create=True)
        if order.state != 'draft':
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order(force_create=True)
        rule = found._dkh_qty_rule()
        line = order.website_order_line.filtered(lambda l: l.product_id.id == product.id)[:1]
        add = rule[1] if line else rule[0]
        order._cart_update(product_id=product.id, add_qty=add)
        request.session['website_sale_cart_quantity'] = order.cart_quantity
        line = order.website_order_line.filtered(lambda l: l.product_id.id == product.id)[:1]
        return {
            'found': True, 'name': found.name, 'qty': int(line.product_uom_qty) if line else 0,
            'url': found.website_url, 'cart_amount': order.amount_untaxed,
        }
