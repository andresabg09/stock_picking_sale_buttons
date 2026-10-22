from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    """Inventario > Operaciones > Inventario físico (conteos).

    Todo lo de fondo es de Odoo: "Pedir recuento" (asigna a quién le toca contar y para cuándo), la columna
    Contado, la Diferencia y "Aplicar". Aquí solo se agrega la foto del producto, un estado de color por línea
    y una regla de seguridad: quien cuenta no aplica. Contar lo puede hacer cualquier usuario de Inventario;
    APLICAR el ajuste (que es lo que cambia la existencia real) solo el Administrador de Inventario."""
    _inherit = 'stock.quant'

    dk_image = fields.Binary(related='product_id.image_128', string='Foto')
    dk_state = fields.Selection(
        [('pending', 'Sin contar'), ('ok', 'Contado'), ('diff', 'Con diferencia')],
        compute='_compute_dk_state', string='Conteo')

    @api.depends('inventory_quantity_set', 'inventory_diff_quantity')
    def _compute_dk_state(self):
        for quant in self:
            if not quant.inventory_quantity_set:
                quant.dk_state = 'pending'
            elif quant.inventory_diff_quantity:
                quant.dk_state = 'diff'
            else:
                quant.dk_state = 'ok'

    def _dk_check_can_apply(self):
        if self.env.uid == SUPERUSER_ID or self.env.user.has_group('stock.group_stock_manager'):
            return
        raise UserError('Solo el Administrador de Inventario puede aplicar ajustes de inventario. '
                        'Tú puedes contar: escribe la cantidad en "Contado" y avisa para que la revise y la aplique.')

    def action_apply_inventory(self):
        self._dk_check_can_apply()
        return super().action_apply_inventory()

    @api.model_create_multi
    def create(self, vals_list):
        # "Existencia" editable directo (pantalla Actualizar cantidad) aplica el ajuste al instante
        if any('inventory_quantity_auto_apply' in vals for vals in vals_list):
            self._dk_check_can_apply()
        return super().create(vals_list)

    def write(self, vals):
        if 'inventory_quantity_auto_apply' in vals:
            self._dk_check_can_apply()
        return super().write(vals)
