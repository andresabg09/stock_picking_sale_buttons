from odoo import models, fields
from odoo.exceptions import UserError

from .sale_order import PAYMENT_METHOD_SELECTION


class SaleConfirmPaymentWizard(models.TransientModel):
    _name = 'sale.confirm.payment.wizard'
    _description = 'Forma de Pago y fecha especial de entrega antes de confirmar'

    sale_order_id = fields.Many2one('sale.order', string='Orden de venta', required=True, readonly=True)
    payment_method = fields.Selection(
        PAYMENT_METHOD_SELECTION,
        string='Forma de Pago',
        help='Obligatoria para poder confirmar la orden (se valida al confirmar, no '
             'al abrir el pop-up — así no explota si un cliente nuevo no tiene forma '
             'de pago previa que precargar). Se precarga con la última forma de pago '
             'usada por este cliente, pero se puede cambiar.',
    )
    special_delivery_date = fields.Date(
        string='Fecha especial de entrega',
        help='Solo si el cliente pidió la mercancía en un día distinto al normal '
             '(antes o después). Si se deja vacía, se entrega en el plazo normal '
             '(3-4 días hábiles).',
    )

    def action_confirm(self):
        """Guarda Forma de Pago (y la fecha especial, si se cargó) en la
        orden y recién ahí la confirma de verdad, saltándose el chequeo
        que abrió este mismo pop-up (ya no hace falta, ya se llenó)."""
        self.ensure_one()
        if not self.payment_method:
            raise UserError("Selecciona la Forma de Pago para poder confirmar la orden.")

        self.sale_order_id.write({
            'custom_payment_method': self.payment_method,
            'custom_special_delivery_date': self.special_delivery_date,
        })
        self.sale_order_id.with_context(skip_payment_method_check=True).action_confirm()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
