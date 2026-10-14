import logging
from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Correos de bodega por defecto (editables en la ventana). Falta la 3.ª persona: Andrés la dará después.
ROUTE_SHEET_EMAIL_TO = 'dianazuniga@diankegroup.com, anyelidperez@diankegroup.com'
ROUTE_SHEET_STATES = ('bodega', 'ruta')


class DkRouteSheetWizard(models.TransientModel):
    _name = 'dk.route.sheet.wizard'
    _description = 'Armar hoja de ruta'

    move_ids = fields.Many2many(
        'account.move', 'dk_route_wizard_move_rel', 'wizard_id', 'move_id', string='Pedidos')
    departure = fields.Datetime(
        string='Salida (fecha y hora)', required=True, default=fields.Datetime.now,
        help='Hoy u otro día, con hora. Si es una hora futura, los pedidos siguen "En bodega" y pasan '
             'solos a "En ruta" cuando llegue esa hora.')
    driver_name = fields.Char(string='Repartidor')
    email_to = fields.Char(string='Enviar a', default=ROUTE_SHEET_EMAIL_TO)
    email_cc = fields.Char(string='Con copia (CC)')
    subject = fields.Char(string='Asunto', help='Si lo dejas vacío se arma solo con la fecha y la cantidad de pedidos.')
    body = fields.Html(
        string='Mensaje', sanitize_attributes=False,
        default='<p>Adjunto la hoja de ruta. Los pedidos marcados como <b>REINTENTO</b> ya salieron '
                'en una ruta anterior y siguen "En ruta".</p>')

    # ---- ayudas ----
    def _lines_data(self):
        """Una fila por pedido, ya ordenada por ruta y por posición del cliente en la ruta."""
        Sheet = self.env['sale.order']
        rows = []
        for move in self.move_ids:
            partner = move.partner_id
            ship = move.partner_shipping_id or partner
            ruta, orden = Sheet._dianke_route_info(partner)
            parts = [ship.street, ship.street2, ship.city, ship.state_id.name, ship.country_id.name]
            prev = self.env['dk.route.sheet.line'].search([('move_id', '=', move.id)], order='id desc', limit=1)
            is_retry = move.custom_delivery_state == 'ruta'
            note = ''
            if is_retry:
                note = _('REINTENTO — ya salió el %s', fields.Date.to_string(prev.sheet_id.date)
                         if prev else _('(fecha no registrada)'))
            paid = move.payment_state in ('paid', 'in_payment')
            rows.append({
                'move_id': move.id,
                'partner_id': partner.id,
                'route_name': ruta or '',
                'route_order': orden or 0,
                'address': ', '.join(p for p in parts if p),
                'waze_link': Sheet._dianke_waze_link(ship) or '',
                'total': move.amount_total,
                'to_collect': 0.0 if paid else move.amount_residual,
                'is_retry': is_retry,
                'retry_note': note,
            })
        # Mismo criterio que el Excel de Dianke: sin ruta o sin posición (0) va al final.
        rows.sort(key=lambda r: (r['route_name'] == '', r['route_name'], r['route_order'] == 0,
                                 r['route_order'], r['partner_id']))
        return rows

    def action_send(self):
        self.ensure_one()
        if not self.move_ids:
            raise UserError(_('No hay pedidos en la hoja de ruta.'))
        if not self.email_to:
            raise UserError(_('Falta el correo destino. Complétalo antes de enviar.'))
        invalid = self.move_ids.filtered(
            lambda m: m.move_type != 'out_invoice' or m.state != 'posted'
            or m.custom_delivery_state not in ROUTE_SHEET_STATES)
        if invalid:
            raise UserError(_(
                'Solo pueden ir en una hoja de ruta los pedidos "En bodega" o "En ruta" (reintentos). '
                'No aplica a: %s', ', '.join(invalid.mapped('name'))))

        already = self.env['dk.route.sheet.line'].search(
            [('move_id', 'in', self.move_ids.ids), ('sheet_id.state', '=', 'programada')])
        if already:
            raise UserError(_(
                'Estos pedidos ya están en una hoja de ruta programada: %s. Cancela esa salida primero si quieres '
                'cambiarla.', '; '.join('%s (%s)' % (l.move_id.name, l.sheet_id.name) for l in already)))

        local = fields.Datetime.context_timestamp(self, self.departure)
        immediate = self.departure <= fields.Datetime.now() + timedelta(minutes=1)
        rows = self._lines_data()
        sheet = self.env['dk.route.sheet'].create({
            'date': local.date(),
            'departure': self.departure,
            'state': 'salio' if immediate else 'programada',
            'driver_name': self.driver_name,
            'email_to': self.email_to,
            'email_cc': self.email_cc,
            'sent_by': self.env.user.id,
            'sent_date': fields.Datetime.now(),
            'move_ids': [(6, 0, self.move_ids.ids)],
            'line_ids': [(0, 0, dict(row, sequence=i * 10)) for i, row in enumerate(rows, start=1)],
        })

        pdf, _fmt = self.env['ir.actions.report']._render_qweb_pdf(
            'stock_picking_sale_buttons.action_report_route_sheet', sheet.ids)
        attachment = self.env['ir.attachment'].create({
            'name': 'Hoja de ruta %s.pdf' % sheet.name.replace('/', '-'),
            'type': 'binary',
            'raw': pdf,
            'mimetype': 'application/pdf',
            'res_model': 'dk.route.sheet',
            'res_id': sheet.id,
        })
        sheet.attachment_id = attachment

        when = local.strftime('%d/%m/%Y %H:%M')
        subject = self.subject or _('Hoja de ruta %(date)s — %(n)s pedidos', date=when, n=len(rows))
        salida = (_('<p><b>Salida:</b> %s</p>', when) if immediate else
                  _('<p><b>Salida programada:</b> %s. Los pedidos pasan a "En ruta" a esa hora.</p>', when))
        mail = self.env['mail.mail'].create({
            'subject': subject,
            'body_html': salida + (self.body or ''),
            'email_to': self.email_to,
            'email_cc': self.email_cc or '',
            'email_from': self.env.user.email_formatted or False,
            'attachment_ids': [(6, 0, attachment.ids)],
            'model': 'dk.route.sheet',
            'res_id': sheet.id,
        })
        # Si el correo falla se levanta el error y TODO se deshace: los pedidos no cambian de estado.
        mail.send(raise_exception=True)

        # Solo después de enviar el correo. Si la salida es ahora, lo que estaba "En bodega" pasa a "En ruta"
        # (los reintentos, ya "En ruta", se quedan como están). Si es futura, los pedidos siguen "En bodega" y
        # el cron (o el aviso exacto de abajo) los pasa a "En ruta" cuando llegue la hora.
        if immediate:
            self.move_ids._dk_move_delivery('ruta', ('bodega',))
        for move in self.move_ids:
            move.message_post(body=_('Incluido en la hoja de ruta %(name)s (salida %(date)s).',
                                     name=sheet.name, date=when))
        sheet.message_post(body=_('Enviada a %s.', self.email_to))
        if not immediate:
            cron = self.env.ref('stock_picking_sale_buttons.ir_cron_dk_depart_sheets', raise_if_not_found=False)
            if cron:
                try:
                    cron.sudo()._trigger(at=self.departure)  # ejecución exacta a la hora de salida
                except Exception:
                    _logger.warning('No se pudo programar la ejecución exacta; lo hará el cron periódico.')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dk.route.sheet',
            'res_id': sheet.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
