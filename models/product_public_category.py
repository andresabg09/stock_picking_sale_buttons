from datetime import timedelta

from odoo import api, fields, models
from odoo.osv import expression


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    @api.model
    def _dk_top_categories(self, limit=8, days=90):
        """Las categorías de la tienda que más se venden (líneas de pedido confirmado en los
        últimos `days` días, sin contar regalos a precio cero). Se actualiza sola con las
        ventas; si no hay ventas, devuelve vacío y quien llama usa el orden normal."""
        Line = self.env['sale.order.line'].sudo()
        since = fields.Datetime.now() - timedelta(days=days)
        groups = Line._read_group(
            [('state', 'in', ('sale', 'done')), ('create_date', '>=', since), ('price_unit', '>', 0)],
            ['product_id'], ['__count'])
        per_template = {}
        for product, count in groups:
            if product:
                tmpl_id = product.product_tmpl_id.id
                per_template[tmpl_id] = per_template.get(tmpl_id, 0) + count
        if not per_template:
            return self.browse()
        score = {}
        for tmpl in self.env['product.template'].sudo().browse(list(per_template)).exists():
            for cat in tmpl.public_categ_ids:
                score[cat.id] = score.get(cat.id, 0) + per_template[tmpl.id]
        if not score:
            return self.browse()
        website = self.env['website'].get_current_website()
        cats = self.search(expression.AND([
            website.website_domain(), [('id', 'in', list(score)), ('parent_id', '=', False)]]))
        return cats.sorted(key=lambda c: (-score[c.id], c.sequence))[:limit]
