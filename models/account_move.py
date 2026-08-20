from odoo import models, fields, api


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
    custom_extra_description = fields.Text(
        string='Nota del vendedor',
        compute='_compute_custom_extra_description',
    )

    @api.depends('name', 'product_id', 'product_id.name', 'product_id.default_code')
    def _compute_custom_extra_description(self):
        # 'name' suele traer, en la primera línea, el nombre del producto
        # (con o sin código) auto-generado por Odoo, seguido de la nota que
        # agregó el vendedor. Aquí se quita esa primera línea repetida para
        # quedarse solo con la nota real.
        for line in self:
            raw = (line.name or '').strip('\n')
            if not raw or not line.product_id:
                line.custom_extra_description = raw or False
                continue
            text_lines = raw.split('\n')
            first_line = text_lines[0].strip()
            product_name = (line.product_id.name or '').strip()
            candidates = {product_name}
            if line.product_id.default_code:
                candidates.add(f"[{line.product_id.default_code}] {product_name}")
            if first_line in candidates:
                text_lines = text_lines[1:]
            remainder = '\n'.join(l for l in text_lines if l.strip())
            line.custom_extra_description = remainder or False
