from odoo import _, fields, models
from odoo.exceptions import UserError

# Correos de bodega por defecto (editables en la ventana). Falta la 3.ª persona: Andrés la dará después.
ROUTE_SHEET_EMAIL_TO = 'dianazuniga@diankegroup.com, anyelidperez@diankegroup.com'
ROUTE_SHEET_STATES = ('bodega', 'ruta')


class DkRouteSheetWizard(models.TransientModel):
    _name = 'dk.route.sheet.wizard'
    _description = 'Armar hoja de ruta'

    move_ids = fields.Many2many(
        'account.move', 'dk_route_wizard_move_rel', 'wizard_id', 'move_id', string='Pedidos')
    route_date = fields.Date(string='Fecha de salida', required=True, default=fields.Date.context_today)
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

        rows = self._lines_data()
        sheet = self.env['dk.route.sheet'].create({
            'date': self.route_date,
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

        subject = self.subject or _('Hoja de ruta %(date)s — %(n)s pedidos',
                                    date=fields.Date.to_string(self.route_date), n=len(rows))
        mail = self.env['mail.mail'].create({
            'subject': subject,
            'body_html': self.body or '',
            'email_to': self.email_to,
            'email_cc': self.email_cc or '',
            'email_from': self.env.user.email_formatted or False,
            'attachment_ids': [(6, 0, attachment.ids)],
            'model': 'dk.route.sheet',
            'res_id': sheet.id,
        })
        # Si el correo falla se levanta el error y TODO se deshace: los pedidos no cambian de estado.
        mail.send(raise_exception=True)

        # Solo después de enviar: lo que estaba "En bodega" pasa a "En ruta". Los reintentos (ya
        # "En ruta") se quedan como están.
        self.move_ids._dk_move_delivery('ruta', ('bodega',))
        for move in self.move_ids:
            move.message_post(body=_('Incluido en la hoja de ruta %(name)s (salida %(date)s).',
                                     name=sheet.name, date=fields.Date.to_string(self.route_date)))
        sheet.message_post(body=_('Enviada a %s.', self.email_to))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dk.route.sheet',
            'res_id': sheet.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
