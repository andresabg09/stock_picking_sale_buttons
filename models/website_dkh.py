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

    def dkh_brands(self):
        """Marcas del cintillo: parámetro `dkh.brands` (separadas por coma), editable sin código."""
        raw = self.env['ir.config_parameter'].sudo().get_param('dkh.brands') or ''
        brands = [b.strip() for b in raw.split(',') if b.strip()]
        return brands or ['Nevada', 'Skala', 'Salon Line', 'NNP', 'X.Care', 'Eleve']

    def dkh_is_designer(self):
        return self.env.user.has_group('website.group_website_designer')

    def dkh_today(self):
        from odoo import fields
        return fields.Date.context_today(self).isoformat()

    def dkh_photo_enabled(self):
        """El modo foto del Pedido rápido solo se ofrece si el servidor tiene la clave de la API."""
        import os
        return bool(os.environ.get('ANTHROPIC_API_KEY'))

