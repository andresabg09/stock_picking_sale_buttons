from odoo import models
from odoo.http import request

PARAM_ENABLED = 'dkh.enabled'
COOKIE = 'dkh_preview'


class Website(models.Model):
    _inherit = 'website'

    def dki_active(self):
        """¿Esta visita ve la Versión I (diseño anterior refinado, con las funciones de la H)?

        Para todos si `dki.enabled` vale 1; solo para quien entró por /dki (cookie `dki_preview`).
        La Versión I usa la misma estructura y funciones que la H (clase `dkh`) con otra "piel" (`dki`)."""
        if self.env['ir.config_parameter'].sudo().get_param('dki.enabled') == '1':
            return True
        try:
            return bool(request and request.httprequest.cookies.get('dki_preview') == '1')
        except RuntimeError:
            return False

    def dkh_active(self):
        """¿Esta visita ve la estructura nueva (encabezado, menú app, funciones)?

        - La Versión I la usa siempre que está activa.
        - La Versión H: para todos si `dkh.enabled` vale 1, o solo para quien entró por /dkh (cookie).
        Los clientes que no entraron por /dkh ni /dki siguen viendo la tienda de siempre."""
        if self.dki_active():
            return True
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

