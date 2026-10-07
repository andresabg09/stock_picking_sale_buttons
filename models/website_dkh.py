from odoo import models
from odoo.http import request

PARAM_ENABLED = 'dkh.enabled'
COOKIE = 'dkh_preview'


class Website(models.Model):
    _inherit = 'website'

    def dkh_active(self):
        """¿Esta visita ve la Versión H?

        - Para todos, si el parámetro del sistema `dkh.enabled` vale 1 (el día del cambio).
        - Solo para quien entró por /dkh (vista previa): queda una cookie en su navegador.
        Los clientes que no entraron por /dkh siguen viendo la tienda de siempre.
        """
        if self.env['ir.config_parameter'].sudo().get_param(PARAM_ENABLED) == '1':
            return True
        try:
            return bool(request and request.httprequest.cookies.get(COOKIE) == '1')
        except RuntimeError:  # fuera de una petición web (cron, shell)
            return False
