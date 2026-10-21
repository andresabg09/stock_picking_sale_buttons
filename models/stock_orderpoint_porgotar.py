from odoo import api, fields, models


class StockWarehouseOrderpoint(models.Model):
    """Compras > Por agotar = las reglas de reabastecimiento NATIVAS de Odoo (Inventario > Operaciones >
    Reabastecimiento), filtradas a la bodega de Dianke y con las reglas que ya llegaron a su mínimo.

    El mínimo es la alarma y el máximo es hasta cuánto se pide ("pedir de más" = subir el máximo). El botón
    "Orden", "Posponer" y "Automatizar" son los de Odoo. Aquí solo se agregan columnas informativas (Nevada,
    comprometido, por llegar, estado) y el filtro "Por agotar".

    Pronóstico (`qty_forecast`) = en bodega + por llegar - comprometido, en la ubicación de la regla; por eso
    Nevada nunca se mezcla (su bodega no tiene reglas)."""
    _inherit = 'stock.warehouse.orderpoint'

    dk_image = fields.Binary(related='product_id.image_128', string='Foto')
    dk_committed = fields.Float(compute='_compute_dk_flows', string='Comprometido', digits='Product Unit of Measure')
    dk_incoming = fields.Float(compute='_compute_dk_flows', string='Por llegar', digits='Product Unit of Measure')
    dk_nevada_label = fields.Char(related='product_id.dk_nevada_label', string='Nevada')
    dk_nevada_tone = fields.Char(related='product_id.dk_nevada_tone')
    dk_state = fields.Selection([('out', 'Agotado'), ('low', 'Por agotar')], compute='_compute_dk_state', string='Estado')
    dk_below_min = fields.Boolean(compute='_compute_dk_state', search='_search_dk_below_min', string='Por agotar')
    dk_note = fields.Char(compute='_compute_dk_state', string='Nota')

    def _compute_dk_flows(self):
        by_location = {}
        for rule in self:
            by_location.setdefault(rule.location_id, self.browse())
            by_location[rule.location_id] |= rule
        for location, rules in by_location.items():
            flows = {p.id: (p.incoming_qty, p.outgoing_qty)
                     for p in rules.product_id.with_context(location=location.id)}
            for rule in rules:
                rule.dk_incoming, rule.dk_committed = flows.get(rule.product_id.id, (0.0, 0.0))

    @api.depends('qty_forecast', 'product_min_qty', 'product_max_qty')
    def _compute_dk_state(self):
        Product = self.env['product.product']
        for rule in self:
            below = rule.product_min_qty > 0 and rule.qty_forecast <= rule.product_min_qty
            rule.dk_below_min = below
            rule.dk_state = ('out' if rule.qty_forecast <= 0 else 'low') if below else False
            if not below:
                rule.dk_note = ''
                continue
            minimum, maximum = rule.product_min_qty, rule.product_max_qty
            target = max(minimum, maximum)
            target_name = 'máximo' if maximum > minimum else 'mínimo'
            if rule.qty_forecast < 0:
                rule.dk_note = '%s que debes + %s de %s' % (
                    Product._dk_fmt_qty(-rule.qty_forecast), Product._dk_fmt_qty(target), target_name)
            elif rule.qty_forecast == minimum:
                rule.dk_note = 'Está justo en el mínimo'
            else:
                rule.dk_note = 'Para llegar al %s (%s)' % (target_name, Product._dk_fmt_qty(target))

    @api.model
    def _search_dk_below_min(self, operator, value):
        rules = self.search([('product_min_qty', '>', 0)])
        ids = rules.filtered(lambda r: r.qty_forecast <= r.product_min_qty).ids
        positive = (operator == '=') == bool(value)
        return [('id', 'in' if positive else 'not in', ids)]

    @api.model
    def _dk_por_agotar_domain(self):
        own = self.env['product.product']._dk_own_warehouses()
        return [('warehouse_id', 'in', own.ids)]

    @api.model
    def dk_count(self):
        """Cuántas reglas de Dianke llegaron a su mínimo (y no están pospuestas): número del botón del panel."""
        today = fields.Date.context_today(self)
        return self.search_count(self._dk_por_agotar_domain() + [
            ('dk_below_min', '=', True),
            '|', ('snoozed_until', '=', False), ('snoozed_until', '<=', today),
        ])

    @api.model
    def dk_open_por_agotar(self):
        """La pantalla nativa de Reabastecimiento, sin crear reglas nuevas (la acción de menú de Odoo crea una
        regla "Manual" por cada producto con pronóstico negativo), limitada a Dianke y ya filtrada."""
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_orderpoint_replenish')
        action.update({
            'name': 'Por agotar',
            'domain': self._dk_por_agotar_domain(),
            'context': {'search_default_dk_por_agotar': True, 'search_default_filter_not_snoozed': True},
        })
        return action
