from odoo import api, fields, models


class ProductProduct(models.Model):
    """Texto corto de existencias para las tarjetas del catálogo de Ventas.

    Usa lo DISPONIBLE (`free_qty` = en bodega menos lo ya reservado), no lo que hay en bodega: así el
    vendedor sabe de un vistazo si le queda o no. Se arma aquí (y no en la vista) para mostrar cifras
    enteras y un texto corto que quepa en una línea, también en celular."""
    _inherit = 'product.product'

    dk_stock_label = fields.Char(compute='_compute_dk_stock_label')
    dk_stock_tone = fields.Char(compute='_compute_dk_stock_label')   # danger | warning | success
    dk_stock_extra = fields.Char(compute='_compute_dk_stock_label')  # "13 reservados"

    @staticmethod
    def _dk_fmt_qty(qty):
        qty = round(qty or 0.0, 2)
        if float(qty).is_integer():
            return '%d' % qty
        return ('%.2f' % qty).rstrip('0').rstrip('.')

    @api.depends('is_storable', 'free_qty', 'qty_available')
    def _compute_dk_stock_label(self):
        for product in self:
            if not product.is_storable:
                product.dk_stock_label = ''
                product.dk_stock_tone = ''
                product.dk_stock_extra = ''
                continue
            free = product.free_qty
            on_hand = product.qty_available
            if free <= 0:
                label, tone = 'Sin existencia', 'danger'
            elif free <= 5:
                label, tone = 'Quedan %s' % product._dk_fmt_qty(free), 'warning'
            else:
                label, tone = 'Disponible: %s' % product._dk_fmt_qty(free), 'success'
            reserved = on_hand - free
            product.dk_stock_label = label
            product.dk_stock_tone = tone
            product.dk_stock_extra = (
                '%s reservados' % product._dk_fmt_qty(reserved) if on_hand > 0 and reserved > 0.0001 else ''
            )
