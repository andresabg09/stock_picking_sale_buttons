from odoo import api, fields, models


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
