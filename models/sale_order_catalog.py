from odoo import models


class SaleOrderCatalog(models.Model):
    """Catálogo de productos de Ventas (botón "Catálogo" de la cotización).

    Agrega a cada producto la MISMA leyenda de promoción que ya muestra la columna "Promo" de las
    líneas de la cotización (`sale.order.line.custom_promo_status`: "✅ Tienes 2 promos completas…" /
    "⏳ Faltan 4 unidades…"), para verla mientras se agregan productos sin salir del catálogo."""
    _inherit = 'sale.order'

    def _dk_catalog_promo_status(self):
        """{product_id: leyenda de promo} de las líneas de esta cotización que participan en una promo."""
        self.ensure_one()
        status = {}
        for line in self.order_line:
            if line.display_type or not line.product_id:
                continue
            text = line.custom_promo_status
            if text:
                status[line.product_id.id] = text
        return status

    def _get_product_catalog_order_line_info(self, product_ids, **kwargs):
        wanted = list(product_ids)  # el método base va quitando ids de la lista que recibe
        info = super()._get_product_catalog_order_line_info(product_ids, **kwargs)
        status = self._dk_catalog_promo_status()
        for product_id in wanted:
            if product_id in info:
                info[product_id]['promoStatus'] = status.get(product_id, '')
        return info
