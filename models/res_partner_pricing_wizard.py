from collections import defaultdict

from odoo import models, fields


class ResPartnerPricingWizard(models.TransientModel):
    _name = 'res.partner.pricing.wizard'
    _description = 'Traer precios pactados de facturas anteriores (por cliente)'

    partner_ids = fields.Many2many(
        'res.partner',
        string='Clientes pendientes de procesar',
    )
    current_partner_id = fields.Many2one('res.partner', string='Cliente actual', readonly=True)
    current_pricelist_name = fields.Char(
        string='Ya tiene asignada esta lista de precios',
        readonly=True,
        help='Se llena solo si el cliente actual ya tiene una lista de precios '
             'distinta a la que genera este wizard — si guardas, se reemplaza.',
    )
    remaining_count = fields.Integer(string='Clientes restantes después de este', readonly=True)
    line_ids = fields.One2many(
        'res.partner.pricing.wizard.line', 'wizard_id',
        string='Productos facturados a este cliente',
    )

    def _fetch_pricing_lines_for_partner(self, partner):
        """Busca en las facturas de cliente ya contabilizadas (out_invoice,
        posted) todos los productos vendidos a `partner`, y arma por
        producto un resumen de los precios distintos que se le han
        cobrado (agrupando por precio redondeado a 2 decimales para que
        diferencias de centésimas de redondeo no cuenten como precios
        distintos). Devuelve una lista de tuplas
        (product, resumen_texto, precio_mas_reciente)."""
        move_lines = self.env['account.move.line'].search([
            ('move_id.partner_id', '=', partner.id),
            ('move_id.move_type', '=', 'out_invoice'),
            ('move_id.state', '=', 'posted'),
            ('product_id', '!=', False),
            ('display_type', '=', False),
        ])

        por_producto = defaultdict(list)
        for line in move_lines:
            por_producto[line.product_id].append(line)

        resultado = []
        for product, lines in por_producto.items():
            por_precio = defaultdict(lambda: {'count': 0, 'ultima_fecha': None})
            for line in lines:
                precio = round(line.price_unit, 2)
                info = por_precio[precio]
                info['count'] += 1
                fecha = line.move_id.invoice_date or line.move_id.date
                if fecha and (not info['ultima_fecha'] or fecha > info['ultima_fecha']):
                    info['ultima_fecha'] = fecha

            precios_ordenados = sorted(
                por_precio.items(),
                key=lambda kv: kv[1]['ultima_fecha'] or fields.Date.from_string('1900-01-01'),
                reverse=True,
            )
            resumen = ' · '.join(
                f"${precio:.2f} (x{info['count']}, última {info['ultima_fecha'] or '?'})"
                for precio, info in precios_ordenados
            )
            precio_mas_reciente = precios_ordenados[0][0] if precios_ordenados else product.lst_price
            resultado.append((product, resumen, precio_mas_reciente))

        return resultado

    def action_open_next_partner(self):
        """Salta automáticamente los clientes sin productos facturados
        (nada que revisar) y abre el wizard en el primero que sí tenga
        historial. Sigue el mismo patrón que
        purchase.bulk.email.wizard.action_open_next_partner: reescribe
        self y regresa el mismo act_window con res_id=self.id para
        refrescar el pop-up en el lugar."""
        pending = self.partner_ids
        while pending:
            partner = pending[0]
            pending = pending - partner
            datos = self._fetch_pricing_lines_for_partner(partner)
            if not datos:
                continue

            pricelist_actual = partner.property_product_pricelist
            aviso = ''
            if pricelist_actual and pricelist_actual.custom_partner_id != partner:
                aviso = pricelist_actual.name

            self.write({
                'partner_ids': [(6, 0, pending.ids)],
                'current_partner_id': partner.id,
                'current_pricelist_name': aviso,
                'remaining_count': len(pending),
                'line_ids': [(5, 0, 0)] + [(0, 0, {
                    'product_id': product.id,
                    'historial_precios': resumen,
                    'precio_elegido': precio_sugerido,
                    'incluir': True,
                }) for product, resumen, precio_sugerido in datos],
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner.pricing.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        # No queda ningún cliente con facturas — nada que revisar, se cierra.
        self.write({
            'partner_ids': [(6, 0, [])],
            'current_partner_id': False,
            'current_pricelist_name': '',
            'remaining_count': 0,
            'line_ids': [(5, 0, 0)],
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_save_and_continue(self):
        """Arma (o actualiza) la lista de precios pactados del cliente
        actual a partir de las líneas marcadas 'incluir', se la asigna, deja
        aviso en su chatter, y pasa al siguiente cliente pendiente."""
        self.ensure_one()
        partner = self.current_partner_id
        if not partner:
            return self.action_open_next_partner()

        lineas_incluidas = self.line_ids.filtered('incluir')

        Pricelist = self.env['product.pricelist']
        pricelist = Pricelist.search([('custom_partner_id', '=', partner.id)], limit=1)
        if not pricelist:
            pricelist = Pricelist.create({
                'name': f"Precios pactados - {partner.display_name}",
                'custom_partner_id': partner.id,
            })
        else:
            pricelist.item_ids.unlink()

        for linea in lineas_incluidas:
            self.env['product.pricelist.item'].create({
                'pricelist_id': pricelist.id,
                'applied_on': '0_product_variant',
                'product_id': linea.product_id.id,
                'compute_price': 'fixed',
                'fixed_price': linea.precio_elegido,
            })

        partner.write({'property_product_pricelist': pricelist.id})
        partner.message_post(body=(
            f"Se actualizó su lista de precios pactados ({len(lineas_incluidas)} "
            "producto(s)) a partir del historial de facturas — Claude Code."
        ))

        return self.action_open_next_partner()

    def action_skip_partner(self):
        """No toca nada del cliente actual, pasa al siguiente."""
        return self.action_open_next_partner()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}


class ResPartnerPricingWizardLine(models.TransientModel):
    _name = 'res.partner.pricing.wizard.line'
    _description = 'Línea de producto/precio del wizard de precios pactados'

    wizard_id = fields.Many2one(
        'res.partner.pricing.wizard', required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    historial_precios = fields.Char(string='Precios vistos en facturas', readonly=True)
    precio_elegido = fields.Float(string='Precio a pactar', digits='Product Price')
    incluir = fields.Boolean(string='Incluir', default=True)
