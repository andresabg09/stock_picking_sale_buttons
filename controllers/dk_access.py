import logging
import time
from urllib.parse import quote

from odoo import http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request

from odoo.addons.stock_picking_sale_buttons.models.res_partner_access import EMAIL_RE, dk_mask_email

_logger = logging.getLogger(__name__)

WHATSAPP = 'https://wa.me/50768337354'
_HITS = {}  # {clave: [momentos]}: tope de envíos de correo por hora (por correo y por IP, en este proceso)


def _allow(key, limit, window=3600):
    now = time.time()
    hits = [t for t in _HITS.get(key, []) if now - t < window]
    if len(hits) >= limit:
        _HITS[key] = hits
        return False
    hits.append(now)
    _HITS[key] = hits
    return True


def _wa_url(text):
    return '%s?text=%s' % (WHATSAPP, quote(text))


class DkAuthSignup(AuthSignupHome):
    """Registro abierto, pero SIN duplicar clientes:
    - si el correo ya es de un contacto/usuario: no se crea nada, se ofrece mandarle el enlace a ese correo;
    - si el negocio (RUC o nombre) ya existe con otro correo: no se crea ni se conecta nada solo, porque el RUC y el
      nombre son públicos; se le pide comunicarse con el equipo para que lo vinculen;
    - si es nuevo: se crea su contacto y su cuenta como siempre."""

    @http.route()
    def web_auth_signup(self, *args, **kw):
        if request.httprequest.method == 'POST' and not kw.get('token'):
            Partner = request.env['res.partner'].sudo()
            email = Partner._dk_norm_email(kw.get('login'))
            if Partner._dk_find_by_email(email):
                return request.render('stock_picking_sale_buttons.dk_access_page', {
                    'state': 'exists', 'email': email, 'masked': dk_mask_email(email)})
            business = Partner._dk_find_business(kw.get('name'), kw.get('dk_vat'))
            if business:
                text = 'Hola, quiero vincular mi cuenta de la tienda al negocio %s. Mi correo es %s.' % (
                    (kw.get('name') or '').strip(), email)
                return request.render('stock_picking_sale_buttons.dk_access_page', {
                    'state': 'team', 'wa_url': _wa_url(text)})
        return super().web_auth_signup(*args, **kw)

    def _signup_with_values(self, token, values):
        super()._signup_with_values(token, values)
        # RUC y WhatsApp del formulario de registro (Odoo deja en `qcontext` solo sus propios campos, por eso se leen
        # de los datos del formulario). Se guardan DESPUÉS de crear la cuenta y sin que un fallo aquí la tumbe.
        vat = (request.params.get('dk_vat') or '').strip()
        phone = (request.params.get('dk_phone') or '').strip()
        if token or not (vat or phone):
            return
        try:
            user = request.env['res.users'].sudo().search([('login', '=', values.get('login'))], limit=1)
            vals = {k: v for k, v in (('vat', vat), ('phone', phone)) if v}
            if user and vals:
                user.partner_id.write(vals)
                request.env.cr.commit()
        except Exception:
            _logger.exception('No se pudo guardar el RUC/WhatsApp del registro de %s', values.get('login'))


class DkAccess(http.Controller):

    @http.route('/shop/dk/acceso', type='http', auth='public', website=True, sitemap=False, methods=['GET', 'POST'])
    def acceso(self, email='', **kw):
        """"Recibir enlace por correo": primera vez, o clave olvidada."""
        values = {'state': 'form', 'email': (email or '').strip()}
        if request.httprequest.method == 'POST':
            values.update(self._send(values['email']))
        return request.render('stock_picking_sale_buttons.dk_access_page', values)

    def _send(self, email):
        Partner = request.env['res.partner'].sudo()
        email = Partner._dk_norm_email(email)
        if not EMAIL_RE.match(email):
            return {'state': 'form', 'error': 'Escribe un correo válido.'}
        ip = request.httprequest.remote_addr or '-'
        if not (_allow('mail:' + email, 3) and _allow('ip:' + ip, 15)):
            return {'state': 'throttled'}
        partners = Partner._dk_find_by_email(email)
        if not partners:
            return {'state': 'notfound', 'email': email}
        target = Partner._dk_pick_target(partners)
        if not target:
            return {'state': 'team', 'wa_url': _wa_url('Hola, mi correo %s aparece en más de un negocio. Necesito ayuda para entrar a la tienda.' % email)}
        try:
            target._dk_send_shop_link(email)
        except Exception:  # correo que no sale (servidor de correo, etc.): no se deja al cliente sin respuesta
            _logger.exception('No se pudo mandar el enlace de acceso a la tienda a %s', email)
            return {'state': 'error', 'wa_url': _wa_url('Hola, no me llegó el enlace para crear mi clave de la tienda. Mi correo es %s.' % email)}
        return {'state': 'sent', 'email': email, 'masked': dk_mask_email(email)}

    # ---- Pedido sin cuenta ----------------------------------------------------------------------------------

    @http.route('/shop/dk/enviar', type='http', auth='public', website=True, sitemap=False, methods=['POST'])
    def enviar(self, **kw):
        """"Enviar mi pedido" (sin iniciar sesión): el carrito pasa a cotización ENVIADA, el cliente ve el
        agradecimiento y el carrito queda vacío. Así tú distingues un pedido enviado de un carrito abandonado."""
        order = request.website.sale_get_order()
        if not order or not order.website_order_line or order.state != 'draft':
            return request.redirect('/shop/cart')
        if order._dkh_min_missing() > 0:
            return request.redirect('/shop/cart')
        public = request.env.user._is_public()
        sudo = order.sudo()
        sudo.action_quotation_sent()
        sudo.message_post(body='Pedido enviado desde la tienda web%s.' % (' sin iniciar sesión' if public else ''))
        request.website.sale_reset()
        request.session['dk_sent_order'] = sudo.name
        return request.redirect('/shop/dk/gracias')

    @http.route('/shop/dk/gracias', type='http', auth='public', website=True, sitemap=False)
    def gracias(self, **kw):
        return request.render('stock_picking_sale_buttons.dk_thanks_page', {
            'order_name': request.session.get('dk_sent_order'),
            'wa_url': _wa_url('Hola, acabo de enviar un pedido desde la tienda.'),
        })
