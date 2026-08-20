from odoo import models, fields, api
from odoo.exceptions import UserError

FIXED_CC = (
    "ventas@shalompma.com,"
    "Dianazuniga@diankegroup.com,"
    "ventasdianke@gmail.com,"
    "milciades@shalompma.com,"
    "andres@shalompma.com,"
    "luis@shalompma.com,"
    "argelis@shalompma.com"
)


class PurchaseBulkEmailWizard(models.TransientModel):
    _name = 'purchase.bulk.email.wizard'
    _description = 'Enviar Órdenes de Compra Individuales por Proveedor'

    purchase_order_ids = fields.Many2many(
        'purchase.order',
        string='Órdenes pendientes (todas, incluye las ya procesadas)',
    )
    current_partner_id = fields.Many2one('res.partner', string='Proveedor actual', readonly=True)
    current_order_ids = fields.Many2many(
        'purchase.order',
        'purchase_bulk_wizard_current_rel',
        string='Órdenes de este proveedor',
        readonly=True,
    )
    remaining_count = fields.Integer(string='Proveedores restantes', readonly=True)
    partner_id = fields.Many2one(related='current_partner_id', string='Para', readonly=True)
    email_to = fields.Char(string='Correo destino')
    email_cc = fields.Char(string='Con copia (CC)')
    subject = fields.Char(string='Asunto')
    body = fields.Html(string='Cuerpo del correo', sanitize_attributes=False)
    attachment_ids = fields.Many2many('ir.attachment', string='Adjuntos')

    @staticmethod
    def _saludo_por_hora():
        """Mañana: 5am-12pm, Tarde: 12pm-7pm, Noche: 7pm-5am (hora del servidor)."""
        hora = fields.Datetime.now().hour
        if 5 <= hora < 12:
            return "Muy buenos días equipo"
        elif 12 <= hora < 19:
            return "Muy buenas tardes equipo"
        else:
            return "Muy buenas noches equipo"

    @staticmethod
    def _build_cc_for_partner(email_to):
        """Devuelve la lista fija de CC, quitando cualquier correo que ya
        sea el destinatario principal (comparación insensible a mayúsculas)."""
        email_to_clean = (email_to or '').strip().lower()
        cc_list = [c.strip() for c in FIXED_CC.split(',') if c.strip()]
        cc_filtered = [c for c in cc_list if c.strip().lower() != email_to_clean]
        return ", ".join(cc_filtered)

    def _build_subject_and_body(self, group):
        """Construye asunto y cuerpo con el formato de Andrés, incluyendo
        todas las órdenes de compra y de venta del grupo (mismo proveedor)."""
        po_names = group.mapped('name')

        so_names = []
        for order in group:
            if order.origin:
                for part in order.origin.split(','):
                    so_name = part.strip().split('/')[0].strip()
                    if so_name and so_name not in so_names:
                        so_names.append(so_name)

        po_str = ", ".join(po_names)
        so_str = ", ".join(so_names) if so_names else "N/A"

        subject = "Pedidos de la ruta de [ESCRIBIR RUTA AQUÍ] - Ordenes de compras %s" % po_str

        saludo = self._saludo_por_hora()

        body = """
<div style="margin: 0px; padding: 0px;">
    <p style="margin: 0px; padding: 0px; font-size: 13px;">
        %s,
        <br/><br/>
        Les adjunto la ruta de <strong>[ESCRIBIR RUTA AQUÍ]</strong> de las órdenes de venta
        <strong>%s</strong> (órdenes de compra <strong>%s</strong>)
        correspondiente a los precios de <strong>[SELECCIONAR LISTA DE PRECIOS]</strong>.
        <br/><br/>
        Así mismo, solicitamos su especial atención a las siguientes especificaciones de despacho:
        <br/><br/>
        <ul>
            <li>Presentación de Productos NNP: Los artículos Aliset NNP de 69gr y Decolorantes se solicitan como unidades individuales.</li>
            <li>En cambio los AER POCKETS se encuentran por <strong>DISPLAYS</strong>.</li>
        </ul>
        <br/>
        Quedo a su disposición ante cualquier consulta adicional.
        <br/><br/>
        ¿Podría confirmar que recibió esta orden?
        <br/><br/>
        Atentamente,<br/>
        Andrés Gutiérrez<br/>
        Asistente<br/>
        Shalom Panamá.
        <br/><br/>
    </p>
</div>
""" % (saludo, so_str, po_str)

        return subject, body

    def action_open_next_partner(self):
        """Toma el primer proveedor con órdenes pendientes, genera los XLSX
        de todas sus órdenes, y muestra el wizard listo para enviar."""
        pending = self.purchase_order_ids
        if not pending:
            return {'type': 'ir.actions.act_window_close'}

        first_partner = pending[0].partner_id
        group = pending.filtered(lambda o: o.partner_id.id == first_partner.id)
        remaining = pending - group

        attachment_ids = []
        for order in group:
            filename = order._xlsx_filename_for_order(order)
            attachment = order._generate_xlsx_attachment(filename=filename)
            attachment_ids.append(attachment.id)

        subject, body = self._build_subject_and_body(group)

        remaining_partners = remaining.mapped('partner_id')
        email_to = first_partner.email or ''
        email_cc = self._build_cc_for_partner(email_to)

        self.write({
            'purchase_order_ids': [(6, 0, remaining.ids)],
            'current_partner_id': first_partner.id,
            'current_order_ids': [(6, 0, group.ids)],
            'remaining_count': len(remaining_partners),
            'email_to': email_to,
            'email_cc': email_cc,
            'subject': subject,
            'body': body,
            'attachment_ids': [(6, 0, attachment_ids)],
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.bulk.email.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_send_and_continue(self):
        """Envía el correo al proveedor actual (con todos sus adjuntos y CC
        fijo) y abre automáticamente el siguiente proveedor pendiente."""
        self.ensure_one()

        if not self.email_to:
            raise UserError("El proveedor no tiene correo configurado. Complétalo antes de enviar.")

        mail_values = {
            'subject': self.subject or '',
            'body_html': self.body or '',
            'email_to': self.email_to,
            'email_cc': self.email_cc or '',
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
            'model': 'purchase.order',
            'res_id': self.current_order_ids[0].id if self.current_order_ids else False,
        }
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()

        return self.action_open_next_partner()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
