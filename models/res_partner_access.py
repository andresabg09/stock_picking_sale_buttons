import html
import re
import unicodedata

from odoo import api, models
from odoo.exceptions import UserError

EMAIL_RE = re.compile(r'^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$')
SHOP_NAME = 'Dianke Group'


def dk_mask_email(email):
    """s*****@gmail.com: el correo nunca se muestra completo a quien no es su dueño."""
    local, _sep, domain = (email or '').partition('@')
    return '%s%s@%s' % (local[:1], '*' * max(len(local) - 1, 3), domain)


def dk_norm_name(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]', '', text)


def dk_norm_vat(text):
    """RUC sin guiones ni espacios; devuelve (completo, sin el dígito verificador "DV")."""
    raw = re.sub(r'[^a-z0-9]', '', (text or '').lower())
    base = raw.split('dv', 1)[0] if 'dv' in raw else raw
    return raw, base


class ResPartner(models.Model):
    """Acceso de los clientes a la tienda web (Odoo lo llama "portal"): solo ven SU información (pedidos,
    cuenta), nunca los módulos de gestión. El enlace es el de Odoo (token firmado): al abrirlo el cliente elige su
    clave y Odoo crea o actualiza su usuario de portal ligado a ESTE contacto, así que no se duplica nada."""
    _inherit = 'res.partner'

    @api.model
    def _dk_norm_email(self, email):
        return (email or '').strip().lower()

    @api.model
    def _dk_company_partners(self):
        return self.env['res.company'].sudo().search([]).partner_id

    @api.model
    def _dk_find_by_email(self, email):
        """Contactos (activos) que ya usan ese correo, o cuyo usuario entra con él. Vacío si el correo no es válido."""
        email = self._dk_norm_email(email)
        if not EMAIL_RE.match(email):
            return self.browse()
        partners = self.sudo().search([('email', 'ilike', email)])
        partners = partners.filtered(lambda p: self._dk_norm_email(p.email) == email)
        users = self.env['res.users'].sudo().search([('login', 'ilike', email)])
        users = users.filtered(lambda u: self._dk_norm_email(u.login) == email)
        return (partners | users.partner_id) - self._dk_company_partners()

    @api.model
    def _dk_pick_target(self, partners):
        """El contacto al que se le manda el enlace. Falso si los contactos son de negocios distintos
        (no adivinamos: lo resuelve el equipo)."""
        if len(partners.mapped('commercial_partner_id')) != 1:
            return self.browse()
        return (partners.filtered('user_ids') or partners)[:1]

    @api.model
    def _dk_find_business(self, name, vat):
        """¿Ya existe un negocio con ese RUC o ese nombre? Solo negocios (sin contacto padre) que son clientes o
        ya tienen acceso. Devuelve el negocio o vacío."""
        want_name = dk_norm_name(name)
        want_vat, want_base = dk_norm_vat(vat)
        if not want_name and not want_vat:
            return self.browse()
        companies = self._dk_company_partners()
        candidates = self.sudo().search([('parent_id', '=', False), '|', ('customer_rank', '>', 0), ('user_ids', '!=', False)])
        for partner in candidates - companies:
            if want_name and dk_norm_name(partner.name) == want_name:
                return partner
            if want_vat and partner.vat:
                have_vat, have_base = dk_norm_vat(partner.vat)
                if have_vat == want_vat or (len(want_base) >= 5 and have_base == want_base):
                    return partner
        return self.browse()

    def _dk_send_shop_link(self, email_to=None):
        """Manda por correo el enlace para crear (o cambiar) la clave de la tienda."""
        self.ensure_one()
        partner = self.sudo()
        to = (email_to or partner.email or '').strip()
        if not EMAIL_RE.match(to.lower()):
            raise UserError('Este contacto no tiene un correo válido. Escríbelo en su ficha y vuelve a intentar.')
        partner.signup_prepare(signup_type='signup')
        url = partner._get_signup_url_for_action()[partner.id]
        company = partner.company_id or self.env.company.sudo()
        body = (
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#0B1F3A;max-width:520px">'
            '<p>Hola, %(name)s.</p>'
            '<p>Te enviamos este enlace para que crees tu propia clave y entres a la tienda de %(shop)s. '
            'Con tu cuenta ves tus pedidos anteriores y haces tus pedidos a nombre de tu negocio.</p>'
            '<p style="margin:26px 0"><a href="%(url)s" style="background:#0B1F3A;color:#ffffff;text-decoration:none;'
            'padding:13px 24px;border-radius:10px;font-weight:bold">Crear mi clave</a></p>'
            '<p style="font-size:13px;color:#475569">El enlace sirve por unos días. Si tú no lo pediste, ignora este correo: '
            'nadie podrá entrar sin abrirlo.</p></div>'
        ) % {'name': html.escape(partner.name or ''), 'shop': SHOP_NAME, 'url': html.escape(url, quote=True)}
        mail = self.env['mail.mail'].sudo().create({
            'subject': 'Crea tu clave para la tienda de %s' % SHOP_NAME,
            'body_html': body,
            'email_to': to,
            'email_from': company.email_formatted or self.env['ir.mail_server'].sudo()._get_default_from_address(),
            'auto_delete': True,
        })
        mail.send(raise_exception=True)
        return True

    def action_dk_send_shop_access(self):
        """Botón de la ficha del contacto: manda el acceso a la tienda al correo que tiene anotado."""
        self.ensure_one()
        if not self.env.user._is_internal():
            raise UserError('Solo el equipo de Dianke puede mandar accesos a la tienda.')
        email = self._dk_norm_email(self.email)
        if not EMAIL_RE.match(email):
            raise UserError('Anota primero el correo del contacto en su ficha (el que te da el cliente).')
        self._dk_send_shop_link(email)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Acceso enviado',
                'message': 'Le mandamos el enlace para crear su clave a %s.' % dk_mask_email(email),
                'type': 'success',
                'sticky': False,
            },
        }
