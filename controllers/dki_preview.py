from odoo import http
from odoo.http import request

COOKIE = 'dki_preview'
ONE_MONTH = 60 * 60 * 24 * 30


class DkiPreview(http.Controller):
    """Vista previa privada de la Versión I (diseño anterior refinado + funciones de la H).

    /dki           -> la enciende en ESTE navegador y lleva al inicio.
    /dki?off=1     -> la apaga.
    /dki?next=/shop -> igual, pero aterriza en esa página (solo rutas internas)."""

    @http.route('/dki', type='http', auth='public', website=True, sitemap=False)
    def preview(self, off=None, next='/inicio', **kw):
        target = next if isinstance(next, str) and next.startswith('/') and not next.startswith('//') else '/inicio'
        response = request.redirect(target)
        if off:
            response.delete_cookie(COOKIE)
        else:
            response.set_cookie(COOKIE, '1', max_age=ONE_MONTH, httponly=True, samesite='Lax')
        return response
