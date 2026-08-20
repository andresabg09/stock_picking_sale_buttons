from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

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
    custom_product_default_code = fields.Char(
        related='product_id.default_code',
        string='Código',
        readonly=True,
    )
