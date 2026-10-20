from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dk_min_qty = fields.Float(
        string='Mínimo en bodega', digits='Product Unit of Measure',
        help='Cuando lo que te queda (en bodega, menos lo ya vendido, más lo que viene en camino) llega a este '
             'número o baja de él, el producto aparece en Compras > Por agotar. 0 = sin aviso.')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _dk_own_forecast(self):
        """{id del producto: {'on_hand', 'incoming', 'outgoing', 'available'}} contando SOLO las bodegas de Dianke
        (nunca la de Nevada, aunque los vendedores tengan las dos empresas activas).

        `available` = en bodega + por llegar - comprometido (lo vendido y aún sin entregar); puede ser negativo."""
        result = {p.id: {'on_hand': 0.0, 'incoming': 0.0, 'outgoing': 0.0, 'available': 0.0} for p in self}
        for warehouse in self._dk_own_warehouses():
            for product in self.with_context(warehouse_id=warehouse.id):
                values = result[product.id]
                values['on_hand'] += product.qty_available
                values['incoming'] += product.incoming_qty
                values['outgoing'] += product.outgoing_qty
                values['available'] += product.virtual_available
        return result
