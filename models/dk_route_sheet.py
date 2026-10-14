import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class DkRouteSheet(models.Model):
    """Hoja de ruta: la lista de pedidos que salen a repartirse (la ve el repartidor y la bodega).

    Se crea al enviar la ventana "Armar hoja de ruta" (wizard). Guarda una foto de cada línea
    (cliente, dirección, cuánto cobrar) para que el PDF y el historial no cambien después."""
    _name = 'dk.route.sheet'
    _description = 'Hoja de ruta'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Número', default='Nuevo', readonly=True, copy=False)
    date = fields.Date(string='Fecha de salida', required=True, default=fields.Date.context_today)
    departure = fields.Datetime(
        string='Salida (fecha y hora)',
        help='Cuándo sale la ruta. Si es una hora futura, los pedidos pasan solos a "En ruta" al llegar esa hora.')
    state = fields.Selection(
        [('programada', 'Programada'), ('salio', 'Salió'), ('cancelada', 'Cancelada')],
        string='Estado', default='salio', required=True, tracking=True)
    driver_name = fields.Char(string='Repartidor')
    line_ids = fields.One2many('dk.route.sheet.line', 'sheet_id', string='Pedidos')
    move_ids = fields.Many2many(
        'account.move', 'dk_route_sheet_move_rel', 'sheet_id', 'move_id',
        string='Pedidos incluidos', readonly=True)
    email_to = fields.Char(string='Enviada a', readonly=True)
    email_cc = fields.Char(string='Con copia', readonly=True)
    sent_by = fields.Many2one('res.users', string='Enviada por', readonly=True)
    sent_date = fields.Datetime(string='Enviada el', readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='PDF', readonly=True)
    line_count = fields.Integer(string='Pedidos', compute='_compute_totals')
    retry_count = fields.Integer(string='Reintentos', compute='_compute_totals')
    total_to_collect = fields.Float(string='Total por cobrar', digits=(16, 2), compute='_compute_totals')

    @api.depends('line_ids', 'line_ids.to_collect', 'line_ids.is_retry')
    def _compute_totals(self):
        for sheet in self:
            sheet.line_count = len(sheet.line_ids)
            sheet.retry_count = len(sheet.line_ids.filtered('is_retry'))
            sheet.total_to_collect = sum(sheet.line_ids.mapped('to_collect'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('dk.route.sheet') or 'Nuevo'
        return super().create(vals_list)

    # ---- salida programada ----
    def _dk_mark_departed(self):
        """Llegó la hora de salida: lo que sigue "En bodega" pasa a "En ruta" y la hoja queda como "Salió".
        Los pedidos que ya no estén "En bodega" (por ejemplo ya se entregaron o se devolvieron) se dejan como están."""
        for sheet in self:
            moves = sheet.move_ids.filtered(
                lambda m: m.move_type == 'out_invoice' and m.state == 'posted'
                and m.custom_delivery_state == 'bodega')
            moves._dk_move_delivery('ruta', ('bodega',))
            for move in moves:
                move.message_post(body=_('Salió en la hoja de ruta %s.', sheet.name))
            sheet.state = 'salio'
            sheet.message_post(body=_('Llegó la hora de salida: %s pedidos pasaron a "En ruta".', len(moves)))

    @api.model
    def _cron_dk_depart_sheets(self):
        """Cron: despacha las hojas programadas cuya hora de salida ya llegó."""
        now = fields.Datetime.now()
        for sheet in self.search([('state', '=', 'programada'), ('departure', '<=', now)]):
            try:
                with self.env.cr.savepoint():
                    sheet._dk_mark_departed()
            except Exception:  # una hoja con problema no debe frenar a las demás
                _logger.exception('No se pudo despachar la hoja de ruta %s', sheet.name)

    def action_cancel_scheduled(self):
        """Cancela una salida programada: los pedidos se quedan "En bodega", sin cambios."""
        for sheet in self.filtered(lambda r: r.state == 'programada'):
            sheet.state = 'cancelada'
            sheet.message_post(body=_('Salida programada cancelada. Los pedidos siguen "En bodega".'))
        return True


class DkRouteSheetLine(models.Model):
    _name = 'dk.route.sheet.line'
    _description = 'Línea de hoja de ruta'
    _order = 'sheet_id, sequence, id'

    sheet_id = fields.Many2one('dk.route.sheet', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    move_id = fields.Many2one('account.move', string='Pedido', index=True)
    partner_id = fields.Many2one('res.partner', string='Cliente')
    route_name = fields.Char(string='Ruta')
    route_order = fields.Integer(string='Orden en la ruta')
    address = fields.Char(string='Dirección')
    waze_link = fields.Char(string='Waze')
    total = fields.Float(string='Total', digits=(16, 2))
    to_collect = fields.Float(string='Por cobrar', digits=(16, 2))
    is_retry = fields.Boolean(string='Reintento')
    retry_note = fields.Char(string='Nota')
