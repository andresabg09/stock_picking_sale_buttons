from odoo import http
from odoo.http import request

COOKIE = 'dkh_preview'
ONE_MONTH = 60 * 60 * 24 * 30


class DkhPreview(http.Controller):
    """Vista previa privada de la Versión H.

    /dkh          -> enciende la vista previa en ESTE navegador y lleva al inicio.
    /dkh?off=1    -> la apaga.
    /dkh?next=/shop -> igual, pero aterriza en esa página (solo rutas internas).
    Los clientes no la ven: solo quien pasó por aquí (o todos, si `dkh.enabled` = 1)."""

    @http.route('/dkh', type='http', auth='public', website=True, sitemap=False)
    def preview(self, off=None, next='/inicio', **kw):
        target = next if isinstance(next, str) and next.startswith('/') and not next.startswith('//') else '/inicio'
        response = request.redirect(target)
        if off:
            response.delete_cookie(COOKIE)
        else:
            response.set_cookie(COOKIE, '1', max_age=ONE_MONTH, httponly=True, samesite='Lax')
        return response
