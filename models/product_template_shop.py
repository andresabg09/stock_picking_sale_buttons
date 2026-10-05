from datetime import timedelta

from odoo import api, fields, models

NEW_DAYS_PARAM = 'stock_picking_sale_buttons.new_days'
NEW_DAYS_DEFAULT = 30


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dk_is_new = fields.Boolean(
        string='Producto nuevo (tienda)',
        compute='_compute_dk_is_new',
        help='Marca "Nuevo" en la tienda: creado hace menos de 30 días. Los días se '
             'cambian con el parámetro del sistema stock_picking_sale_buttons.new_days.',
    )

    @api.depends('create_date')
    def _compute_dk_is_new(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(NEW_DAYS_PARAM)
        try:
            days = int(raw) if raw else NEW_DAYS_DEFAULT
        except ValueError:
            days = NEW_DAYS_DEFAULT
        limit = fields.Datetime.now() - timedelta(days=days)
        for tmpl in self:
            tmpl.dk_is_new = bool(tmpl.create_date and tmpl.create_date >= limit)
