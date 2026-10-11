from odoo import http
from odoo.http import request


class CatalogPromo(http.Controller):
    """Refresca la leyenda de promoción del catálogo de Ventas después de cada cambio de cantidad.

    Una promo "compra X llévate Y" suma varios productos, así que al cambiar uno puede cambiar la
    leyenda de los demás: el catálogo pide todas las leyendas de nuevo y actualiza las tarjetas."""

    @http.route('/stock_picking_sale_buttons/catalog/promo_status', type='json', auth='user')
    def promo_status(self, order_id, **kwargs):
        order = request.env['sale.order'].browse(int(order_id))
        if not order.exists():
            return {}
        return order._dk_catalog_promo_status()
