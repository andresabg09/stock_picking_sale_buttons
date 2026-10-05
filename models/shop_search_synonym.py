import re
import unicodedata

from odoo import api, fields, models
from odoo.osv import expression

# Abreviaturas y palabras de hasta este largo se buscan como palabra completa
# (" shp "), para que "est" no encuentre "forest". Las más largas, como texto suelto.
SHORT_WORD_LEN = 4


def normalize_text(text):
    """Minúsculas, sin tildes ni signos: 'Açaí-X.Care' -> 'acai x care'."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


class ShopSearchSynonym(models.Model):
    _name = 'shop.search.synonym'
    _description = 'Sinónimos de búsqueda de la tienda'
    _order = 'name'

    name = fields.Char(
        string='Grupo',
        required=True,
        help='Nombre para reconocer el grupo (ej. "Shampú"). No se usa al buscar.',
    )
    words = fields.Text(
        string='Palabras equivalentes',
        required=True,
        help='Palabras que significan lo mismo, separadas por coma (ej. "shp, shampu, '
             'champu, shampoo"). Si el cliente escribe cualquiera de ellas, se '
             'encuentran los productos que tengan cualquiera de las otras. No importan '
             'mayúsculas ni tildes.',
    )
    active = fields.Boolean(default=True)

    @api.model
    def _get_groups(self):
        """Lista de grupos, cada uno como lista de palabras ya normalizadas."""
        groups = []
        for rec in self.sudo().search([]):
            words = []
            for raw in re.split(r'[,;\n]+', rec.words or ''):
                word = normalize_text(raw)
                if word and word not in words:
                    words.append(word)
            if len(words) > 1:
                groups.append(words)
        return groups

    @api.model
    def _term_domain(self, term):
        """Subdominio sobre `search_index` para UNA palabra escrita por el cliente.

        Se suma (OR) a la búsqueda normal de Odoo, así que nunca quita resultados:
        solo agrega los que coinciden sin importar tildes, con la palabra pegada
        ("xcare"), por código de barras, o por sinónimo ("champú" -> "SHP").
        """
        norm = normalize_text(term)
        if not norm:
            return [('id', '=', 0)]

        variants = {norm}
        # singular simple: tintes -> tinte, jabones -> jabon
        if len(norm) > 4 and norm.endswith('es'):
            variants.add(norm[:-2])
        if len(norm) > 3 and norm.endswith('s'):
            variants.add(norm[:-1])

        patterns = set(variants)
        if len(norm) >= 4:
            # "x care" o "x.care" escrito como "xcare"
            patterns.add(norm.replace(' ', ''))

        for group in self._get_groups():
            for variant in variants:
                if any(w == variant or (len(variant) >= 3 and w.startswith(variant))
                       for w in group):
                    for word in group:
                        patterns.add(' %s ' % word if len(word) <= SHORT_WORD_LEN else word)
                    break

        domains = [[('search_index', 'ilike', pattern)] for pattern in sorted(patterns)]
        return expression.OR(domains)
