from odoo import models, fields, api

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    invoice_count = fields.Integer(
        string='Facturas',
        compute='_compute_invoice_count',
    )
    custom_days_overdue_text = fields.Char(
        string='Días de Vencimiento',
        compute='_compute_custom_days_overdue_text'
    )
    custom_is_overdue = fields.Boolean(
        string='¿Vencido?',
        compute='_compute_custom_days_overdue_text'
    )
    custom_overdue_class = fields.Char(
        string='Clase de Alerta Bootstrap',
        compute='_compute_custom_days_overdue_text'
    )
    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_id:
            return {}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    @api.depends('sale_id')
    def _compute_invoice_count(self):
        for picking in self:
            if picking.sale_id:
                picking.invoice_count = len(picking.sale_id.invoice_ids)
            else:
                picking.invoice_count = 0
    def action_view_invoices(self):
        self.ensure_one()
        if not self.sale_id:
            return {}
        invoices = self.sale_id.invoice_ids
        if len(invoices) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': invoices.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('id', 'in', invoices.ids)],
        }
    @api.depends('scheduled_date', 'date_deadline', 'state')
    def _compute_custom_days_overdue_text(self):
        today = fields.Date.today()
        for picking in self:
            if picking.state in ('done', 'cancel'):
                picking.custom_days_overdue_text = ""
                picking.custom_is_overdue = False
                picking.custom_overdue_class = "text-muted"
                continue
            target_datetime = picking.date_deadline or picking.scheduled_date
            if not target_datetime:
                picking.custom_days_overdue_text = ""
                picking.custom_is_overdue = False
                picking.custom_overdue_class = "text-muted"
                continue
            target_date = target_datetime.date()
            delta = (target_date - today).days
            picking.custom_is_overdue = delta < 0
            if delta < 0:
                picking.custom_days_overdue_text = f"Vencido por {-delta} día(s)"
                picking.custom_overdue_class = "text-danger fw-bold"
            elif delta == 0:
                picking.custom_days_overdue_text = "Vence hoy"
                picking.custom_overdue_class = "text-warning fw-bold"
            else:
                picking.custom_days_overdue_text = f"Quedan {delta} día(s)"
                picking.custom_overdue_class = "text-success fw-bold"


class StockMove(models.Model):
    _inherit = 'stock.move'
    custom_product_image = fields.Binary(
        related='product_id.image_1024',
        string='Imagen',
        readonly=True,
    )
    custom_product_barcode = fields.Char(
        related='product_id.barcode',
        string='Código de Barras',
        readonly=True,
    )
    custom_ready = fields.Boolean(
        string='Listo',
        default=False,
    )

    def _sync_description_from_sale(self):
        for move in self:
            if move.sale_line_id:
                sale_name = move.sale_line_id.name or ''
                product_name = move.product_id.name or ''
                if sale_name.strip() and sale_name.strip() != product_name.strip():
                    move.description_picking = sale_name
                else:
                    move.description_picking = False

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._sync_description_from_sale()
        return moves

    def write(self, vals):
        result = super().write(vals)
        # Si se asigna o cambia la línea de venta, sincronizar descripción
        if 'sale_line_id' in vals:
            self._sync_description_from_sale()
        return result
