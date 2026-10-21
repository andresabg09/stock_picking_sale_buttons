from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # EN DESUSO (v18.0.5.12.0): el mínimo y el máximo viven ahora en las reglas de reabastecimiento nativas de
    # Odoo (Inventario > Operaciones > Reabastecimiento). Ya no sale en ninguna vista; se quita del modelo
    # en una versión futura (primero hay que dejar que Odoo borre las vistas viejas que lo usaban).
    dk_min_qty = fields.Float(string='Mínimo en bodega (en desuso)', digits='Product Unit of Measure')
