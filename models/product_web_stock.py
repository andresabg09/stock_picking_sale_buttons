from odoo import api, fields, models


class ProductProduct(models.Model):
    """Disponibilidad que ve el CLIENTE en la tienda web: lo que hay libre en la bodega de Dianke, SIN contar
    Nevada (su lista es solo informativa para los vendedores). Es la misma cuenta del catálogo de Ventas
    (`_dk_own_stock`). Se calcula con sudo porque el visitante de la tienda no tiene permiso de leer inventario."""
    _inherit = 'product.product'

    dk_web_free_qty = fields.Float(compute='_compute_dk_web_free_qty', digits='Product Unit of Measure')

    def _compute_dk_web_free_qty(self):
        own_stock = self.sudo()._dk_own_stock()
        for product in self:
            product.dk_web_free_qty = own_stock.get(product.id, (0.0, 0.0))[0]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dk_web_free_qty = fields.Float(compute='_compute_dk_web_stock', digits='Product Unit of Measure')
    dk_web_oos = fields.Boolean(compute='_compute_dk_web_stock')          # sin existencia -> se ve apagado
    dk_web_avail_label = fields.Char(compute='_compute_dk_web_stock')     # "Disponible: 40" (vacío si no hay)

    @api.depends('is_storable')
    def _compute_dk_web_stock(self):
        # todas las variantes juntas, en una sola consulta
        self.sudo().product_variant_ids.mapped('dk_web_free_qty')
        for template in self:
            free = sum(v.dk_web_free_qty for v in template.sudo().product_variant_ids)
            template.dk_web_free_qty = free
            template.dk_web_oos = bool(template.is_storable and free <= 0)
            template.dk_web_avail_label = (
                'Disponible: %s' % self.env['product.product']._dk_fmt_qty(free)
                if template.is_storable and free > 0 else ''
            )
