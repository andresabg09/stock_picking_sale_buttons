from odoo import api, fields, models

SLOTS = [
    ('hero', 'Inicio · principal (1600 × 700 px, carrusel)'),
    ('mid', 'Inicio · mediano (1000 × 400 px)'),
    ('small', 'Inicio · pequeño (500 × 400 px)'),
    ('square', 'Inicio · cuadrado, junto a Nuevos (600 × 600 px)'),
    ('tall', 'Inicio · vertical, junto a Lo más pedido (600 × 900 px)'),
    ('shop_top', 'Tienda · franja superior (1600 × 300 px)'),
]


class DkhBanner(models.Model):
    """Espacios de banner de la tienda (Versión H). Se editan desde Ventas → Configuración →
    "Banners de la tienda": sin imagen se ve el diseño rosa/azul con el título y subtítulo."""
    _name = 'dkh.banner'
    _description = 'Banner de la tienda'
    _order = 'slot, sequence, id'

    name = fields.Char(string='Nombre interno', required=True)
    slot = fields.Selection(SLOTS, string='Espacio', required=True, default='hero')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    title = fields.Char(string='Título', translate=True)
    subtitle = fields.Char(string='Subtítulo', translate=True)
    cta_label = fields.Char(string='Texto del botón', translate=True)
    link = fields.Char(string='Enlace', help='Ej. /shop/category/12 o /pedido-rapido')
    image = fields.Image(string='Imagen', max_width=2000, max_height=2000)

    @api.model
    def _dkh_for(self, slot):
        return self.sudo().search([('slot', '=', slot), ('active', '=', True)])
