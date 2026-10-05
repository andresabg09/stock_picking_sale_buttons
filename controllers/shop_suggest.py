from odoo import http
from odoo.http import request
from odoo.tools.misc import format_amount

MAX_SUGGESTIONS = 6


class ShopSuggest(http.Controller):
    """Sugerencias del buscador del encabezado. Reemplaza el autocompletado nativo de Odoo
    (que se trababa al borrar y no cargaba dentro de la tienda): usa el mismo buscador
    tolerante del módulo (sinónimos, tildes, códigos de barras) y devuelve lo mínimo."""

    @http.route('/shop/dk/suggest', type='json', auth='public', website=True, sitemap=False)
    def suggest(self, term='', **kw):
        term = str(term or '').strip()[:80]
        if len(term) < 2:
            return {'items': [], 'total': 0}
        website = request.website
        options = {
            'displayDescription': False, 'displayDetail': False, 'displayExtraLink': False,
            'displayImage': False, 'allowFuzzy': True, 'category': None, 'tags': None,
            'min_price': 0.0, 'max_price': 0.0, 'attrib_values': None,
            'display_currency': website.currency_id,
        }
        count, details, fuzzy = website._search_with_fuzzy(
            'products_only', term, limit=MAX_SUGGESTIONS, order='name asc', options=options)
        found = details[0].get('results') if details else request.env['product.template']
        items = []
        for tmpl in (found or [])[:MAX_SUGGESTIONS]:
            info = tmpl._get_combination_info(only_template=True)
            items.append({
                'name': (tmpl.name or '').capitalize(),
                'url': tmpl.website_url,
                'image': '/web/image/product.template/%s/image_128' % tmpl.id,
                'price': format_amount(request.env, info.get('price') or 0.0, website.currency_id),
            })
        return {'items': items, 'total': count, 'fuzzy': fuzzy or False}
