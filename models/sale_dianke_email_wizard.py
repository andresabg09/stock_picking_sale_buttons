from odoo import models, fields
from odoo.exceptions import UserError


class SaleDiankeEmailWizard(models.TransientModel):
    _name = 'sale.dianke.email.wizard'
    _description = 'Confirmar envío de Excel a Dianke'

    sale_order_ids = fields.Many2many(
        'sale.order',
        string='Órdenes de venta incluidas',
        readonly=True,
    )
    email_to = fields.Char(string='Correo destino')
    email_cc = fields.Char(string='Con copia (CC)')
    subject = fields.Char(string='Asunto')
    body = fields.Html(string='Cuerpo del correo', sanitize_attributes=False)
    attachment_ids = fields.Many2many('ir.attachment', string='Adjuntos (Excel)')

    def action_send(self):
        """Envía el correo con el Excel a Dianke y marca las órdenes
        incluidas como enviadas. Solo se llega aquí después de que el
        usuario revisó/editó el correo en esta ventana."""
        self.ensure_one()

        if not self.email_to:
            raise UserError("Falta el correo destino. Complétalo antes de enviar.")
        if not self.attachment_ids:
            raise UserError("No hay Excel adjunto. Vuelve a abrir el envío desde la orden de venta.")

        mail_values = {
            'subject': self.subject or '',
            'body_html': self.body or '',
            'email_to': self.email_to,
            'email_cc': self.email_cc or '',
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
            'model': 'sale.order',
            'res_id': self.sale_order_ids[0].id if self.sale_order_ids else False,
        }
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()

        self.sale_order_ids.write({
            'custom_dianke_exported': True,
            'custom_dianke_exported_date': fields.Datetime.now(),
        })

        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
