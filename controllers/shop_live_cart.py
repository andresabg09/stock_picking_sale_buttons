from odoo import http
from odoo.http import request
from odoo.osv import expression
from odoo.tools.misc import format_amount

MAX_QTY = 99999


class ShopLiveCart(http.Controller):
    """Cantidad "viva" en las tarjetas de la tienda: lo que el cliente escribe
    queda en el carrito al momento, sin botón de confirmar (la cotización en
    Ventas la crea Odoo, como siempre, al tocar el carrito)."""

    @http.route('/shop/dk/set_qty', type='json', auth='public', website=True, sitemap=False)
    def set_qty(self, product_id, qty, **kw):
        try:
            product_id = int(product_id)
            qty = int(float(qty))
        except (TypeError, ValueError):
            return {'error': 'Cantidad no válida.'}
        qty = max(0, min(qty, MAX_QTY))

        product = request.env['product.product'].sudo().browse(product_id).exists()
        tmpl = product.product_tmpl_id
        allowed = request.env['product.template'].search(
            expression.AND([request.website.sale_product_domain(), [('id', '=', tmpl.id)]]), limit=1)
        if not product or not allowed or tmpl.product_variant_count != 1:
            return {'error': 'Este producto no se puede agregar desde aquí.'}

        if qty > 0:
            # Reglas de compra (mínimo 6; tintes NNP de 5 en 5): se aplican aquí y de nuevo en
            # sale.order._cart_update, así ninguna ruta del carrito las salta.
            qty = tmpl._dkh_normalize_qty(qty)

        order = request.website.sale_get_order(force_create=True)
        if order.state != 'draft':
            # Mismo manejo que /shop/cart/update: carrito ya no editable -> uno nuevo.
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order(force_create=True)

        line = order.website_order_line.filtered(lambda l: l.product_id.id == product.id)[:1]
        if qty > 0:
            order._cart_update(product_id=product.id, set_qty=qty)
        elif line:
            # Llegar a 0 con add_qty negativo borra la línea (así lo hace el "−" del carrito).
            order._cart_update(product_id=product.id, add_qty=-line.product_uom_qty)

        request.session['website_sale_cart_quantity'] = order.cart_quantity
        return self._payload(order, product)

    @staticmethod
    def _payload(order, product):
        currency = order.currency_id
        lines = order.website_order_line
        line = lines.filtered(lambda l: l.product_id.id == product.id)[:1]
        return {
            'qty': int(line.product_uom_qty) if line else 0,
            'line_total': format_amount(request.env, line._get_cart_display_price(), currency) if line else '',
            'cart_quantity': order.cart_quantity,
            'cart_lines': len(lines),
            'cart_amount': order.amount_untaxed,
            'min_missing': order._dkh_min_missing(),
        }
