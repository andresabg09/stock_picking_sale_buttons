from odoo import api, fields, models

from .shop_search_synonym import normalize_text


def _search_extra(env, search_term):
    """Función que Odoo llama por cada palabra buscada (`search_extra` del detalle
    de búsqueda). Corre con el usuario público, por eso el modelo de sinónimos se
    lee con sudo dentro de `_term_domain`."""
    return env['shop.search.synonym']._term_domain(search_term)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    search_index = fields.Text(
        string='Índice de búsqueda de la tienda',
        compute='_compute_search_index',
        store=True,
        copy=False,
        help='Texto interno para que el buscador de la tienda encuentre el producto '
             'sin importar tildes, signos ni abreviaturas: nombre normalizado, nombre '
             'pegado, categorías y todos los códigos de barras (principal y extras). '
             'Se recalcula solo.',
    )

    @api.depends(
        'name',
        'default_code',
        'public_categ_ids.name',
        'product_variant_ids.barcode',
        'product_variant_ids.barcode_ids.name',
    )
    def _compute_search_index(self):
        for tmpl in self:
            name = normalize_text(tmpl.name)
            parts = [name, name.replace(' ', ''), normalize_text(tmpl.default_code)]
            parts += [normalize_text(categ.name) for categ in tmpl.public_categ_ids]
            for variant in tmpl.product_variant_ids:
                parts.append(normalize_text(variant.barcode))
                parts += [normalize_text(code.name) for code in variant.barcode_ids]
            tmpl.search_index = ' %s ' % ' '.join(p for p in parts if p)

    @api.model
    def _search_get_detail(self, website, order, options):
        detail = super()._search_get_detail(website, order, options)
        detail['search_extra'] = _search_extra
        return detail
