import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.osv import expression

from .shop_search_synonym import normalize_text

NEW_DAYS_PARAM = 'stock_picking_sale_buttons.new_days'
NEW_DAYS_DEFAULT = 30

# "1000gr", "665ml", "198g", "1l", "30pza"...: marca el final del nombre de la "línea" del producto.
SIZE_RE = re.compile(r'^\d+([.,]\d+)?(gr|g|kg|ml|l|lt|oz|pza|pzas|und|unid|cm|mm)$')


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

    # ---------------------------------------------------------------- sugerencias de la tienda

    def _dk_shop_domain(self):
        website = self.env['website'].get_current_website()
        return website.sale_product_domain()

    def _dk_family_key(self):
        """Nombre de la "línea" del producto: las palabras hasta la medida.
        'TRAT-SKALA 1000GR ACAI' -> 'trat skala 1000gr'; sin medida: las 2 primeras palabras."""
        self.ensure_one()
        tokens = normalize_text(self.name).split()
        key = []
        for token in tokens:
            key.append(token)
            if SIZE_RE.match(token):
                return ' '.join(key)
        return ' '.join(tokens[:2])

    def _dk_siblings(self, limit=8):
        """Otras fragancias/presentaciones de la misma línea (mismo nombre base)."""
        self.ensure_one()
        key = self._dk_family_key()
        if not key:
            return self.browse()
        domain = expression.AND([
            self._dk_shop_domain(),
            [('id', '!=', self.id), ('search_index', 'ilike', ' %s ' % key)],
        ])
        return self.search(domain, limit=limit, order='name')

    def _dk_also_bought(self, limit=8):
        """Lo que otros clientes compraron en los mismos pedidos que este producto."""
        self.ensure_one()
        Line = self.env['sale.order.line'].sudo()
        states = ('sale', 'done')
        orders = Line.search([
            ('product_id.product_tmpl_id', '=', self.id), ('state', 'in', states),
        ], order='id desc', limit=300).order_id
        if not orders:
            return self.browse()
        groups = Line._read_group(
            [('order_id', 'in', orders.ids), ('state', 'in', states),
             ('product_id.product_tmpl_id', '!=', self.id)],
            ['product_id'], ['__count'], order='__count desc', limit=limit * 4)
        ranked = []
        for product, _count in groups:
            tmpl_id = product.product_tmpl_id.id if product else False
            if tmpl_id and tmpl_id not in ranked:
                ranked.append(tmpl_id)
        found = self.search(expression.AND([self._dk_shop_domain(), [('id', 'in', ranked)]]))
        return found.sorted(key=lambda t: ranked.index(t.id))[:limit]

    def _dk_suggestions(self, limit=8, exclude=None):
        """"Te puede interesar": primero lo que otros compran junto con este producto;
        si faltan, más de su misma categoría; si aún faltan, lo nuevo."""
        self.ensure_one()
        exclude = (exclude or self.browse()) | self
        picked = self._dk_also_bought(limit * 2) - exclude
        picked = picked[:limit]
        if len(picked) < limit and self.public_categ_ids:
            domain = expression.AND([
                self._dk_shop_domain(),
                [('id', 'not in', (exclude | picked).ids),
                 ('public_categ_ids', 'in', self.public_categ_ids.ids)],
            ])
            picked |= self.search(domain, limit=limit - len(picked), order='create_date desc')
        if len(picked) < limit:
            domain = expression.AND([
                self._dk_shop_domain(),
                [('id', 'not in', (exclude | picked).ids)],
            ])
            picked |= self.search(domain, limit=limit - len(picked), order='create_date desc')
        return picked

    # ---------------------------------------------------------------- secciones de la tienda

    @api.model
    def _dk_new_days(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(NEW_DAYS_PARAM)
        try:
            return int(raw) if raw else NEW_DAYS_DEFAULT
        except ValueError:
            return NEW_DAYS_DEFAULT

    @api.model
    def _dk_new_products(self, limit=4):
        """Lo más reciente de la tienda (creado dentro de los días de "Nuevo")."""
        since = fields.Datetime.now() - timedelta(days=self._dk_new_days())
        domain = expression.AND([
            self._dk_shop_domain(),
            [('create_date', '>=', since), ('public_categ_ids', '!=', False)],
        ])
        return self.search(domain, limit=limit, order='create_date desc')

    @api.model
    def _dk_bestsellers(self, limit=4, days=90):
        """Lo más pedido en los últimos `days` días (unidades en pedidos confirmados)."""
        Line = self.env['sale.order.line'].sudo()
        since = fields.Datetime.now() - timedelta(days=days)
        groups = Line._read_group(
            [('state', 'in', ('sale', 'done')), ('create_date', '>=', since), ('price_unit', '>', 0)],
            ['product_id'], ['product_uom_qty:sum'],
            order='product_uom_qty:sum desc', limit=limit * 6)
        ranked = []
        for product, _qty in groups:
            tmpl_id = product.product_tmpl_id.id if product else False
            if tmpl_id and tmpl_id not in ranked:
                ranked.append(tmpl_id)
        if not ranked:
            return self.browse()
        found = self.search(expression.AND([self._dk_shop_domain(), [('id', 'in', ranked)]]))
        return found.sorted(key=lambda t: ranked.index(t.id))[:limit]

    @api.model
    def _dk_cart_suggestions(self, order, limit=4):
        """"Te puede interesar" del carrito: lo que otros compraron junto con lo que ya está en
        el carrito; si faltan, lo nuevo. Nunca repite lo que ya está en el carrito."""
        in_cart = order.website_order_line.product_id.product_tmpl_id if order else self.browse()
        picked = self.browse()
        for tmpl in in_cart[:5]:
            picked |= tmpl._dk_also_bought(limit)
        picked = (picked - in_cart)[:limit]
        if len(picked) < limit:
            extra = self._dk_new_products(limit * 3) - in_cart - picked
            picked |= extra[:limit - len(picked)]
        return picked
