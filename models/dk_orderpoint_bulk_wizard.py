from odoo import api, fields, models
from odoo.exceptions import UserError

from .dkh_rules import rule_for


class DkOrderpointBulkWizard(models.TransientModel):
    """Desde la lista de Productos: poner mínimo y máximo a varios productos de una vez.

    Crea (o actualiza) la regla de reabastecimiento NATIVA de cada producto en la bodega de Dianke, en modo
    Manual (nunca crea pedidos solos), con la ruta Comprar y el múltiplo del producto (tintes NNP de 5, Aliset y
    decolorantes de 12, Pocket de 6) para que "Por ordenar" ya salga en cajas completas."""
    _name = 'dk.orderpoint.bulk.wizard'
    _description = 'Definir mínimo y máximo a varios productos'

    product_tmpl_ids = fields.Many2many('product.template', string='Productos')
    min_qty = fields.Float(string='Mínimo (alarma)', digits='Product Unit of Measure', required=True)
    max_qty = fields.Float(
        string='Máximo (hasta cuánto pedir)', digits='Product Unit of Measure',
        help='Déjalo en 0 para pedir solo hasta el mínimo. Súbelo si quieres surtir de más.')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'product.template' and self.env.context.get('active_ids'):
            values['product_tmpl_ids'] = [(6, 0, self.env.context['active_ids'])]
        return values

    def action_apply(self):
        self.ensure_one()
        if self.min_qty <= 0:
            raise UserError('El mínimo debe ser mayor que 0.')
        maximum = max(self.max_qty, self.min_qty)
        products = self.product_tmpl_ids.product_variant_ids.filtered('is_storable')
        if not products:
            raise UserError('Ninguno de los productos seleccionados maneja inventario.')
        warehouses = self.env['product.product']._dk_own_warehouses()
        if not warehouses:
            raise UserError('No encuentro la bodega de Dianke.')
        Orderpoint = self.env['stock.warehouse.orderpoint'].with_context(active_test=False)
        created = updated = 0
        for warehouse in warehouses:
            existing = {op.product_id.id: op for op in Orderpoint.search([
                ('warehouse_id', '=', warehouse.id), ('product_id', 'in', products.ids)])}
            route = warehouse.buy_pull_id.route_id
            for product in products:
                step = rule_for(product.product_tmpl_id.name, product.product_tmpl_id._dkh_is_tinte())[1]
                vals = {'product_min_qty': self.min_qty, 'product_max_qty': maximum, 'trigger': 'manual', 'active': True}
                if step > 1:
                    vals['qty_multiple'] = step
                rule = existing.get(product.id)
                if rule:
                    if route and not rule.route_id:
                        vals['route_id'] = route.id
                    rule.write(vals)
                    updated += 1
                else:
                    vals.update({'product_id': product.id, 'warehouse_id': warehouse.id,
                                 'location_id': warehouse.lot_stock_id.id})
                    if route:
                        vals['route_id'] = route.id
                    Orderpoint.create(vals)
                    created += 1
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': 'Mínimo y máximo definidos',
                'message': '%d reglas creadas y %d actualizadas. Míralas en Compras > Pedidos > Por agotar.'
                           % (created, updated),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
