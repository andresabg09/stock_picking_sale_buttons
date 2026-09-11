from odoo import models, fields


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    custom_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente (precios pactados)',
        readonly=True,
        copy=False,
        help='Si esta lista la generó "Traer precios pactados de facturas", aquí '
             'queda marcado el cliente al que pertenece — así, la próxima vez que '
             'se corra esa acción sobre el mismo cliente, se actualiza esta misma '
             'lista en vez de crear una duplicada.',
    )
