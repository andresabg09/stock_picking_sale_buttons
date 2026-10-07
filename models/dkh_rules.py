"""Reglas de compra de la tienda (Versión H). Valen en el SERVIDOR: la pantalla solo las refleja.

- Cantidad mínima por producto: 6.
- Tintes NNP: múltiplos de 5, al múltiplo más cercano (22 -> 20, 23 -> 25), nunca menos de 5.
- Aliset 69 gr: de 12 en 12 (docenas). Decolorantes: de 2 en 2. Ambientadores GODREJ POCKET: de 6 en 6.
- Pedido mínimo (solo pedidos de la web): B/. 150 sobre el subtotal sin impuestos
  (parámetro del sistema `dkh.min_order`).

Solo se aplican a pedidos con sitio web (`website_id`): las ventas internas y la app de rutas
no pasan por aquí.
"""
from odoo import models
from odoo.exceptions import ValidationError

MIN_UNITS = 6
TINTE_MIN = 5
TINTE_STEP = 5
ALISET_STEP = 12      # Aliset 69 gr: por docenas
DECOLORANTE_STEP = 2  # decolorantes: de 2 en 2
POCKET_STEP = 6       # ambientadores Pocket: por display de 6
MIN_ORDER_PARAM = 'dkh.min_order'
MIN_ORDER_DEFAULT = 150.0


def normalize_qty(minimum, step, qty):
    """Cantidad válida más cercana a la pedida (múltiplo de `step`, nunca menos de `minimum`).
    0 (o menos) significa "quitar" y no se toca. Ej. step 5: 22 -> 20, 23 -> 25."""
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        return 0
    step = max(1, int(step))
    return max(minimum, ((qty + step // 2) // step) * step)


def rule_for(name, is_tinte=False):
    """(mínimo, salto) según el producto. Por nombre, sin importar mayúsculas."""
    up = (name or '').upper()
    if is_tinte:
        return TINTE_MIN, TINTE_STEP
    if 'ALISET' in up and '69GR' in up.replace(' ', ''):
        return ALISET_STEP, ALISET_STEP
    if 'DECOLORANTE' in up:
        return DECOLORANTE_STEP, DECOLORANTE_STEP
    if 'POCKET' in up and ('GODREJ' in up or 'AER' in up):
        return POCKET_STEP, POCKET_STEP
    return MIN_UNITS, 1


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
        minimum, step = rule_for(self.name, is_tinte)
        return minimum, step, is_tinte

    def _dkh_normalize_qty(self, qty):
        self.ensure_one()
        minimum, step = rule_for(self.name, self._dkh_is_tinte())
        return normalize_qty(minimum, step, qty)


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

    def _check_cart_is_ready_to_be_paid(self):
        """Con la Versión H encendida, el pedido mínimo también se exige en el servidor (aunque
        alguien abra /shop/payment directo por URL). Si Odoo no trae este chequeo, no se usa."""
        for order in self:
            if order.website_id and order.website_id.dkh_active() and order._dkh_min_missing() > 0:
                raise ValidationError(
                    'Todavía no llegas al pedido mínimo: te faltan B/. %.2f.' % order._dkh_min_missing())
        return super()._check_cart_is_ready_to_be_paid()
