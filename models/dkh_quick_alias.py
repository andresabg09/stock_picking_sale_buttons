from odoo import fields, models


class DkhQuickAlias(models.Model):
    """Memoria del Pedido rápido: lo que ESTE cliente escribió ("shp coco") y el producto que
    eligió. La próxima vez que escriba lo mismo se propone ese producto directamente; si no era
    el correcto, "No es este" borra el registro."""
    _name = 'dkh.quick.alias'
    _description = 'Pedido rápido: elección recordada por cliente'
    _order = 'write_date desc'

    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, index=True, ondelete='cascade')
    alias_text = fields.Char(string='Lo que escribió', required=True, index=True)
    template_id = fields.Many2one('product.template', string='Producto', required=True, ondelete='cascade')
    uses = fields.Integer(string='Veces', default=1)

    _sql_constraints = [
        ('partner_alias_uniq', 'unique(partner_id, alias_text)', 'Ya existe esa elección para el cliente.'),
    ]
