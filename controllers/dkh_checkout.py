from odoo import http
from odoo.http import request
from odoo.osv import expression


class DkhCheckout(http.Controller):
    """Escáner de la cámara (Versión H): un código de barras = ese producto en el pedido."""

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
            'cart_lines': len(order.website_order_line),
        }
