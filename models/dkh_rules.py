"""Reglas de compra de la tienda (Versión H). Valen en el SERVIDOR: la pantalla solo las refleja.

- Cantidad mínima por producto: 6.
- Tintes NNP: múltiplos de 5, al múltiplo más cercano (22 -> 20, 23 -> 25), nunca menos de 5.
- Pedido mínimo (solo pedidos de la web): B/. 150 sobre el subtotal sin impuestos
  (parámetro del sistema `dkh.min_order`).

Solo se aplican a pedidos con sitio web (`website_id`): las ventas internas y la app de rutas
no pasan por aquí.
"""
from odoo import models

MIN_UNITS = 6
TINTE_MIN = 5
TINTE_STEP = 5
MIN_ORDER_PARAM = 'dkh.min_order'
MIN_ORDER_DEFAULT = 150.0


def normalize_qty(is_tinte, qty):
    """Cantidad válida más cercana a la pedida. 0 (o menos) significa "quitar" y no se toca."""
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        return 0
    if is_tinte:
        return max(TINTE_MIN, ((qty + 2) // TINTE_STEP) * TINTE_STEP)
    return max(MIN_UNITS, qty)


def qty_rule(is_tinte):
    """(mínimo, salto) que usa la pantalla para el + y el −."""
    return (TINTE_MIN, TINTE_STEP) if is_tinte else (MIN_UNITS, 1)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _dkh_is_tinte(self):
        """Tinte NNP: por nombre, o por categoría interna que diga "tinte" y "nnp"
        (mismo criterio que usa el módulo para el precio mínimo de las promos)."""
        self.ensure_one()
        if 'TINTE NNP' in (self.name or '').upper():
            return True
        cat = self.categ_id
        while cat:
            name = (cat.name or '').lower()
            if 'tinte' in name and 'nnp' in name:
                return True
            cat = cat.parent_id
        return False

    def _dkh_qty_rule(self):
        """(mínimo, salto, es_tinte) para pintar la tarjeta."""
        self.ensure_one()
        is_tinte = self._dkh_is_tinte()
        minimum, step = qty_rule(is_tinte)
        return minimum, step, is_tinte

    def _dkh_normalize_qty(self, qty):
        self.ensure_one()
        return normalize_qty(self._dkh_is_tinte(), qty)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _dkh_is_tinte(self):
        self.ensure_one()
        return self.product_tmpl_id._dkh_is_tinte()

    def _dkh_qty_rule(self):
        self.ensure_one()
        return self.product_tmpl_id._dkh_qty_rule()

    def _dkh_normalize_qty(self, qty):
        self.ensure_one()
        return self.product_tmpl_id._dkh_normalize_qty(qty)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _dkh_min_order_amount(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(MIN_ORDER_PARAM)
        try:
            return float(raw) if raw else MIN_ORDER_DEFAULT
        except ValueError:
            return MIN_ORDER_DEFAULT

    def _dkh_min_missing(self):
        """Cuánto falta para el pedido mínimo (0 si ya se alcanzó o si no es un pedido de la web)."""
        self.ensure_one()
        if not self.website_id:
            return 0.0
        return max(0.0, self._dkh_min_order_amount() - self.amount_untaxed)

    def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """Toda cantidad que entra al carrito de la web pasa por la regla (mínimo 6, tintes de 5
        en 5). Quitar (cantidad final 0) no se toca."""
        if self.website_id and (add_qty or set_qty):
            line = self.env['sale.order.line']
            if line_id:
                line = self.order_line.filtered(lambda l: l.id == int(line_id))[:1]
            elif product_id:
                line = self.order_line.filtered(lambda l: l.product_id.id == int(product_id))[:1]
            product = line.product_id
            if not product and product_id:
                product = self.env['product.product'].browse(int(product_id)).exists()
            if product:
                current = line.product_uom_qty if line else 0
                target = set_qty if set_qty else current + add_qty
                if target > 0:
                    fixed = product._dkh_normalize_qty(target)
                    if fixed != target:
                        set_qty, add_qty = fixed, 0
        return super()._cart_update(
            product_id=product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, **kwargs)
