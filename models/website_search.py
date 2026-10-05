from odoo import models


class Website(models.Model):
    _inherit = 'website'

    def _search_with_fuzzy(self, search_type, search, limit, order, options):
        """Primero se busca lo que escribió el cliente tal cual (ya con sinónimos,
        tildes y códigos de barras). Solo si no hay nada se deja actuar al corrector
        de errores de Odoo. Sin esto, el corrector cambiaba "champú" por otra palabra
        parecida antes de que el sinónimo llegara a probarse."""
        if search and options.get('allowFuzzy', True):
            search_details = self._search_get_details(search_type, order, options)
            count, results = self._search_exact(search_details, search, limit, order)
            if count:
                return count, results, False
        return super()._search_with_fuzzy(search_type, search, limit, order, options)
