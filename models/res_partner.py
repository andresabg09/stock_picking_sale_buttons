from odoo import models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_traer_precios_pactados(self):
        """Botón/acción masiva desde el listado de Contactos: abre el wizard
        que recorre, cliente por cliente, las facturas ya contabilizadas y
        arma su lista de precios pactados a partir de lo que de hecho se le
        cobró en el pasado (sin importar qué vendedor lo hizo)."""
        if not self:
            raise UserError("Selecciona al menos un cliente para traer sus precios pactados.")

        wizard = self.env['res.partner.pricing.wizard'].create({
            'partner_ids': [(6, 0, self.ids)],
        })
        return wizard.action_open_next_partner()
