from odoo import models, fields, api

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    invoice_count = fields.Integer(
        string='Facturas',
        compute='_compute_invoice_count',
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
