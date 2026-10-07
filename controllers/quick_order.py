import base64
import io
import json
import logging
import os
import re

from odoo import http
from odoo.http import request
from odoo.osv import expression

from ..models.shop_search_synonym import normalize_text

_logger = logging.getLogger(__name__)

MAX_LINES = 200
MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 12 * 1024 * 1024
PHOTO_MAX_SIDE = 1600
PHOTO_MODEL = 'claude-haiku-4-5'
PHOTO_PROMPT = (
    'La imagen es una lista de pedido escrita a mano (o impresa) de un cliente de una distribuidora '
    'de productos de belleza en Panamá. Transcríbela EXACTAMENTE, una línea por producto, en el '
    'formato "cantidad x nombre del producto" (si no se ve la cantidad, escribe solo el nombre). '
    'No inventes productos, no corrijas ni expliques, no agregues títulos ni comentarios. Si algo '
    'no se lee, escribe lo que se alcance a ver. Responde solo con las líneas.'
)
MAX_OPTIONS = 8
MAX_QTY = 9999

# "6 x trat skala", "6x trat skala"
QTY_BEFORE = re.compile(r'^(?P<qty>\d{1,4})\s*[xX×*]\s*(?P<text>.+)$')
# "847610010414 x 6", "trat skala x6", "trat skala acai 3" (sin x solo vale hasta 2 cifras,
# para no confundir "shp x.care 665" con 665 unidades)
QTY_AFTER_X = re.compile(r'^(?P<text>.+?)\s*[xX×*]\s*(?P<qty>\d{1,4})$')
QTY_AFTER_BARE = re.compile(r'^(?P<text>.+?)\s+(?P<qty>\d{1,2})$')


class QuickOrder(http.Controller):

    @http.route('/pedido-rapido', type='http', auth='user', website=True, sitemap=False)
    def quick_order_page(self, **kw):
        return request.render('stock_picking_sale_buttons.quick_order_page', {})

    @http.route('/pedido-rapido/revisar', type='http', auth='user', website=True,
                methods=['POST'], sitemap=False)
    def quick_order_review(self, texto='', **kw):
        parsed = self._parse_lines(texto)
        lines = [self._resolve_line(raw, text, qty) for raw, text, qty in parsed[:MAX_LINES]]
        return request.make_json_response({
            'lines': lines,
            'truncated': len(parsed) > MAX_LINES,
        })

    @http.route('/pedido-rapido/foto', type='http', auth='user', website=True,
                methods=['POST'], sitemap=False)
    def quick_order_photo(self, **kw):
        """Modo foto: una o varias fotos de una lista -> texto transcrito por Claude. Las fotos
        NO se guardan: se reducen en memoria, se mandan a la API y se descartan."""
        if not os.environ.get('ANTHROPIC_API_KEY'):
            return request.make_json_response({'error': 'El modo foto todavía no está activado.'}, status=503)
        try:
            import anthropic
        except ImportError:
            return request.make_json_response({'error': 'El modo foto todavía no está instalado en el servidor.'}, status=503)
        files = request.httprequest.files.getlist('fotos')[:MAX_PHOTOS]
        if not files:
            return request.make_json_response({'error': 'Elige al menos una foto.'}, status=400)
        blocks = []
        for storage in files:
            raw = storage.read(MAX_PHOTO_BYTES + 1)
            if not raw or len(raw) > MAX_PHOTO_BYTES:
                continue
            try:
                from PIL import Image, ImageOps
                img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
                img.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=85)
            except Exception:
                continue
            blocks.append({'type': 'image', 'source': {
                'type': 'base64', 'media_type': 'image/jpeg',
                'data': base64.standard_b64encode(buf.getvalue()).decode('ascii')}})
        if not blocks:
            return request.make_json_response({'error': 'No se pudo leer ninguna de las fotos.'}, status=400)
        try:
            client = anthropic.Anthropic(timeout=60.0)
            reply = client.messages.create(
                model=PHOTO_MODEL, max_tokens=2000,
                messages=[{'role': 'user', 'content': blocks + [{'type': 'text', 'text': PHOTO_PROMPT}]}])
        except anthropic.APIError as exc:
            _logger.warning('Pedido rápido por foto: error de la API (%s)', exc)
            return request.make_json_response({'error': 'No pudimos leer la foto ahora. Intenta de nuevo.'}, status=502)
        text = '\n'.join(b.text for b in reply.content if b.type == 'text').strip()
        return request.make_json_response({'texto': text})

    @http.route('/pedido-rapido/olvidar', type='http', auth='user', website=True,
                methods=['POST'], sitemap=False)
    def quick_order_forget(self, alias='', **kw):
        """"No es este": borra lo que se había recordado para esta frase de ESTE cliente."""
        partner = request.env.user.partner_id.commercial_partner_id
        key = normalize_text(alias)
        if key:
            request.env['dkh.quick.alias'].sudo().search(
                [('partner_id', '=', partner.id), ('alias_text', '=', key)]).unlink()
        return request.make_json_response({'ok': True})

    @http.route('/pedido-rapido/agregar', type='http', auth='user', website=True,
                methods=['POST'], sitemap=False)
    def quick_order_add(self, items='[]', **kw):
        try:
            items = json.loads(items)
        except ValueError:
            items = []
        Template = request.env['product.template']
        base_domain = request.website.sale_product_domain()
        order = request.website.sale_get_order(force_create=True)
        if order.state != 'draft':
            # Mismo manejo que /shop/cart/update: si el carrito ya no es editable, uno nuevo.
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order(force_create=True)
        added, skipped = 0, []
        for item in items[:MAX_LINES]:
            try:
                tmpl_id = int(item.get('template_id'))
                qty = max(1, min(int(item.get('qty') or 1), MAX_QTY))
            except (TypeError, ValueError, AttributeError):
                continue
            tmpl = Template.search(expression.AND([base_domain, [('id', '=', tmpl_id)]]), limit=1)
            if not tmpl or tmpl.product_variant_count != 1:
                skipped.append(item.get('name') or tmpl_id)
                continue
            order._cart_update(product_id=tmpl.product_variant_id.id, add_qty=qty)
            added += 1
            if item.get('learn') and item.get('alias'):
                self._remember(item['alias'], tmpl)
        # El numerito del carrito en el encabezado sale de aquí (igual que /shop/cart/update).
        request.session['website_sale_cart_quantity'] = order.cart_quantity
        return request.make_json_response({'added': added, 'skipped': skipped})

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _partner():
        return request.env.user.partner_id.commercial_partner_id

    def _remember(self, alias, tmpl):
        """Guarda (o actualiza) que este cliente, al escribir `alias`, se refiere a `tmpl`."""
        key = normalize_text(alias)
        if not key or len(key) > 120:
            return
        Alias = request.env['dkh.quick.alias'].sudo()
        found = Alias.search([('partner_id', '=', self._partner().id), ('alias_text', '=', key)], limit=1)
        if found:
            found.write({'template_id': tmpl.id, 'uses': found.uses + 1})
        else:
            Alias.create({'partner_id': self._partner().id, 'alias_text': key, 'template_id': tmpl.id})

    def _history(self, templates):
        """{template_id: unidades que este cliente ya compró} para ordenar sugerencias."""
        if not templates:
            return {}
        Line = request.env['sale.order.line'].sudo()
        groups = Line._read_group(
            [('order_id.partner_id.commercial_partner_id', '=', self._partner().id),
             ('state', 'in', ('sale', 'done')),
             ('product_id.product_tmpl_id', 'in', templates.ids)],
            ['product_id'], ['product_uom_qty:sum'])
        hist = {}
        for product, qty in groups:
            hist[product.product_tmpl_id.id] = hist.get(product.product_tmpl_id.id, 0) + qty
        return hist

    def _suggest(self, text):
        """Hasta 3 productos parecidos a una línea no encontrada, primero los que ya compra."""
        Template = request.env['product.template']
        tokens = [t for t in normalize_text(text).split() if len(t) >= 3]
        if not tokens:
            return Template
        domain = expression.OR([[('search_index', 'ilike', t)] for t in tokens])
        found = Template.search(
            expression.AND([request.website.sale_product_domain(), domain]), limit=60)
        if not found:
            return Template
        hist = self._history(found)

        def hits(t):
            idx = normalize_text(t.search_index or t.name)
            return sum(1 for tk in tokens if tk in idx)

        ranked = sorted(found, key=lambda t: (-hits(t), -hist.get(t.id, 0), t.name))
        return Template.browse([t.id for t in ranked[:3]])

    @staticmethod
    def _parse_lines(texto):
        """Devuelve [(línea original, texto a buscar, cantidad)] sin líneas vacías."""
        parsed = []
        for raw in (texto or '').splitlines():
            line = re.sub(r'[\t;]+', ' ', raw).strip()
            if not line:
                continue
            qty = 1
            text = line
            for pattern in (QTY_BEFORE, QTY_AFTER_X, QTY_AFTER_BARE):
                match = pattern.match(line)
                if match and match.group('text').strip():
                    text = match.group('text').strip()
                    qty = max(1, int(match.group('qty')))
                    break
            parsed.append((raw.strip(), text, qty))
        return parsed

    def _option(self, tmpl):
        info = tmpl._get_combination_info(only_template=True)
        return {
            'template_id': tmpl.id,
            'name': tmpl.name,
            'price': info.get('price') or 0.0,
            'image': '/web/image/product.template/%s/image_128' % tmpl.id,
            'url': tmpl.website_url,
            'variants': tmpl.product_variant_count != 1,
            'rule': list(tmpl._dkh_qty_rule()),
        }

    def _resolve_line(self, raw, text, qty):
        Template = request.env['product.template']
        base_domain = request.website.sale_product_domain()
        result = {'raw': raw, 'text': text, 'qty': qty, 'status': 'missing', 'options': [],
                  'fuzzy': False}

        # 0) ¿Ya eligió esto antes? Se propone lo mismo (con "No es este" para corregir).
        alias = request.env['dkh.quick.alias'].sudo().search(
            [('partner_id', '=', self._partner().id), ('alias_text', '=', normalize_text(text))], limit=1)
        if alias:
            remembered = Template.search(expression.AND([base_domain, [('id', '=', alias.template_id.id)]]), limit=1)
            if remembered:
                result['options'] = [self._option(remembered)]
                result['status'] = 'ok'
                result['remembered'] = True
                return result

        # 1) ¿Es un código? Se busca exacto en código de barras, códigos extra y referencia.
        if re.fullmatch(r'[0-9A-Za-z\-]{5,}', text) and re.search(r'\d', text):
            code_domain = ['|', '|',
                           ('product_variant_ids.barcode', '=', text),
                           ('product_variant_ids.barcode_ids.name', '=', text),
                           ('default_code', '=', text)]
            by_code = Template.search(expression.AND([base_domain, code_domain]), limit=MAX_OPTIONS)
            if by_code:
                result['options'] = [self._option(t) for t in by_code]
                result['status'] = 'ok' if len(by_code) == 1 else 'choose'
                return result

        # 2) Por nombre: mismo buscador de la tienda (sinónimos, tildes y corrector).
        options = {
            'displayDescription': False, 'displayDetail': False, 'displayExtraLink': False,
            'displayImage': False, 'allowFuzzy': True, 'category': None, 'tags': None,
            'min_price': 0.0, 'max_price': 0.0, 'attrib_values': None,
            'display_currency': request.website.currency_id,
        }
        count, details, fuzzy = request.website._search_with_fuzzy(
            'products_only', text, limit=MAX_OPTIONS * 4, order='name asc', options=options)
        found = details[0].get('results', Template) if details else Template
        if not found:
            suggestions = self._suggest(text)
            if suggestions:
                result['options'] = [self._option(t) for t in suggestions]
                result['status'] = 'suggest'
            return result

        ranked = self._rank(found, fuzzy or text, self._history(found))[:MAX_OPTIONS]
        result['options'] = [self._option(t) for t in ranked]
        result['fuzzy'] = fuzzy or False
        result['total'] = count
        # Un solo resultado, o uno cuyo nombre es exactamente lo escrito: se da por entendido.
        exact = [t for t in ranked if normalize_text(t.name) == normalize_text(text)]
        result['status'] = 'ok' if (count == 1 or len(exact) == 1) else 'choose'
        if result['status'] == 'ok' and exact:
            result['options'] = [self._option(exact[0])]
        return result

    @staticmethod
    def _rank(templates, text, hist=None):
        """Primero los que contienen TODAS las palabras escritas como palabras completas."""
        words = normalize_text(text).split()

        def score(tmpl):
            tokens = normalize_text(tmpl.name).split()
            whole = all(w in tokens for w in words)
            return (0 if whole else 1, -(hist or {}).get(tmpl.id, 0), len(tokens), tmpl.name)

        return sorted(templates, key=score)
