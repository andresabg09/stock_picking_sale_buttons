from odoo import fields, models


class ProductTemplate(models.Model):
    """Unidades que trae cada bulto (caja) del producto: es la "Unidad de traspaso" de la lista de Nevada
    (ej. "Caja12" = 12 unidades). Es solo informativo, para que el vendedor sepa cuántas unidades trae un
    bulto cuando el cliente pregunta; no cambia precios ni existencias."""
    _inherit = 'product.template'

    dk_bulk_units = fields.Integer(
        string='Unidades por bulto',
        help='Cuántas unidades trae cada bulto (caja) de este producto. Se muestra en el catálogo de Ventas.',
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    dk_bulk_units = fields.Integer(related='product_tmpl_id.dk_bulk_units', string='Unidades por bulto')
