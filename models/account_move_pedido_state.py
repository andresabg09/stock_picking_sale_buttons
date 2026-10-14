from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMovePedidoState(models.Model):
    """Estado de entrega del PEDIDO (la factura de Odoo, ver Glosario en CLAUDE.md).

    Dos ejes que no se pisan:
      * "Dónde está" (custom_delivery_state): En bodega → En ruta → Entregado. Se mueve con botones.
      * "Cobro": sale del pago que ya registra Odoo (payment_state), no se toca a mano.
    La etiqueta única que se ve en listas y filtros (custom_pedido_state) los combina:
    Entregado + pagado = "Entregado y cobrado". Si el cliente pagó antes de la entrega, el pedido
    sigue mostrando dónde está (por ejemplo "En ruta") y la columna de cobro dice "Pagado".
    """
    _inherit = 'account.move'

    custom_delivery_state = fields.Selection(
        [('bodega', 'En bodega'), ('ruta', 'En ruta'), ('entregado', 'Entregado')],
        string='Dónde está', default='bodega', copy=False, tracking=True, index=True,
        help='Un pedido nace "En bodega". Pasa a "En ruta" cuando sale a repartirse y a '
             '"Entregado" cuando el cliente lo recibe. El cobro se toma del pago registrado en Odoo.')
    custom_pedido_state = fields.Selection(
        [('bodega', 'En bodega'), ('ruta', 'En ruta'), ('entregado', 'Entregado'),
         ('cobrado', 'Entregado y cobrado')],
        string='Estado del pedido', compute='_compute_custom_pedido_state', store=True, index=True)

    @api.depends('custom_delivery_state', 'payment_state')
    def _compute_custom_pedido_state(self):
        for move in self:
            state = move.custom_delivery_state or 'bodega'
            if state == 'entregado' and move.payment_state in ('paid', 'in_payment'):
                state = 'cobrado'
            move.custom_pedido_state = state

    def _dk_move_delivery(self, target, sources):
        """Cambia "dónde está" a `target`. Solo pedidos de cliente ya publicados; los que ya están en
        `target` se saltan sin quejarse (para que la acción en lote sea repetible)."""
        invalid = self.filtered(lambda m: m.move_type != 'out_invoice' or m.state != 'posted')
        if invalid:
            raise UserError(_(
                'Solo se puede cambiar el estado de pedidos de cliente ya publicados. No aplica a: %s',
                ', '.join(invalid.mapped(lambda m: m.name or m.display_name))))
        labels = dict(self._fields['custom_delivery_state'].selection)
        blocked = self.filtered(lambda m: m.custom_delivery_state not in sources
                                and m.custom_delivery_state != target)
        if blocked:
            raise UserError(_(
                'No se puede pasar a "%(target)s" desde el estado actual: %(detail)s',
                target=labels[target],
                detail=', '.join('%s (%s)' % (m.name, labels[m.custom_delivery_state]) for m in blocked)))
        todo = self.filtered(lambda m: m.custom_delivery_state != target)
        if todo:
            # sudo solo para escribir: el que cambia el estado queda registrado en el chatter (tracking).
            todo.sudo().write({'custom_delivery_state': target})
        # Recarga la pantalla (lista o formulario) para que se vea el estado nuevo.
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_dk_to_route(self):
        return self._dk_move_delivery('ruta', ('bodega',))

    def action_dk_to_delivered(self):
        return self._dk_move_delivery('entregado', ('bodega', 'ruta'))

    def action_dk_to_bodega(self):
        return self._dk_move_delivery('bodega', ('ruta', 'entregado'))

    def action_dk_undo_delivery(self):
        return self._dk_move_delivery('ruta', ('entregado',))

    def action_dk_open_route_wizard(self):
        """Abre la ventana "Armar hoja de ruta" con los pedidos seleccionados. Entran los "En bodega" y
        los "En ruta" (reintentos: salieron un día y no se pudieron entregar). Los "Entregado" no."""
        invalid = self.filtered(lambda m: m.move_type != 'out_invoice' or m.state != 'posted'
                                or m.custom_delivery_state not in ('bodega', 'ruta'))
        if not self or invalid:
            raise UserError(_(
                'Selecciona pedidos "En bodega" o "En ruta" para armar la hoja de ruta.%s',
                (' No aplica a: %s' % ', '.join(invalid.mapped('name'))) if invalid else ''))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Armar hoja de ruta'),
            'res_model': 'dk.route.sheet.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_ids': [(6, 0, self.ids)]},
        }
