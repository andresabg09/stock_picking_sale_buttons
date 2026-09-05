from odoo import models, fields, api

TINTE_NNP_MIN_PRICE = 1.16

DIANKE_EMAIL_TO = "ventasdianke@gmail.com,Dianazuniga@diankegroup.com"

PAYMENT_METHOD_SELECTION = [
    ('efectivo', 'Efectivo'),
    ('tarjeta', 'Tarjeta'),
    ('credito_1_semana', 'Crédito 1 semana'),
    ('credito_2_semanas', 'Crédito 2 semanas'),
    ('transferencia', 'Transferencia'),
    ('yappy', 'Yappy'),
    ('otro', 'Otro'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_first_product_image = fields.Binary(
        string='Imagen',
        compute='_compute_custom_first_product_image',
        readonly=True,
    )
    custom_payment_method = fields.Selection(
        PAYMENT_METHOD_SELECTION,
        string='Forma de Pago',
        help='Cómo va a pagar el cliente. Se incluye en el reporte que se envía a Dianke.',
    )
    custom_dianke_exported = fields.Boolean(
        string='Enviada a Dianke',
        default=False,
        copy=False,
        help='Se marca automáticamente cuando la orden se incluye en un envío (manual o automático) a Dianke.',
    )
    custom_dianke_exported_date = fields.Datetime(
        string='Fecha envío a Dianke',
        readonly=True,
        copy=False,
    )

    @api.depends('order_line.product_id')
    def _compute_custom_first_product_image(self):
        for order in self:
            first_line = order.order_line.filtered(
                lambda l: l.product_id and l.product_id.image_128
            )[:1]
            order.custom_first_product_image = (
                first_line.product_id.image_128 if first_line else False
            )

    # ------------------------------------------------------------------
    # Exportación a Dianke
    # ------------------------------------------------------------------

    @staticmethod
    def _dianke_contact_info(partner):
        """Devuelve (cliente, ruc, telefono, celular, contacto, direccion)
        para el reporte de Dianke, a partir de los campos estándar de Odoo
        en res.partner."""
        if not partner:
            return ('', '', '', '', '', '')

        # Si el partner es un contacto individual de una empresa, el
        # "Cliente" es la empresa y el "Contacto" es la persona.
        company = partner.commercial_partner_id or partner
        if partner != company and partner.name:
            contacto = partner.name
        else:
            contacto = partner.name or ''

        direccion = ''
        if hasattr(partner, 'contact_address_complete') and partner.contact_address_complete:
            direccion = partner.contact_address_complete
        else:
            direccion = partner._display_address() if partner else ''

        return (
            company.name or '',
            partner.vat or company.vat or '',
            partner.phone or company.phone or '',
            partner.mobile or company.mobile or '',
            contacto,
            direccion,
        )

    def _generate_dianke_xlsx_bytes(self):
        """Genera un único XLSX con todas las órdenes de self, una fila por
        línea de producto, con la información completa del cliente para
        que Dianke pueda subirlo directo a su sistema."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.utils import get_column_letter
        import io

        wb = Workbook()
        ws = wb.active
        ws.title = "Pedidos Dianke"

        headers = [
            "Orden de Venta", "Fecha", "Cliente", "RUC", "Teléfono", "Celular",
            "Contacto", "Dirección", "Forma de Pago", "Código/Referencia",
            "Producto", "Descripción / Notas", "Cantidad", "Precio Unitario",
            "Subtotal", "Foto del Local",
        ]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        payment_labels = dict(PAYMENT_METHOD_SELECTION)
        photo_col = len(headers)  # última columna
        row_idx = 1

        for order in self.sorted(key=lambda o: o.name):
            partner = order.partner_id
            cliente, ruc, telefono, celular, contacto, direccion = self._dianke_contact_info(partner)
            forma_pago = payment_labels.get(order.custom_payment_method, order.custom_payment_method or '')
            fecha = order.date_order.strftime('%d/%m/%Y') if order.date_order else ''

            lines = order.order_line.filtered(lambda l: not l.display_type)
            first_line_of_order = True

            for line in lines:
                row_idx += 1
                product = line.product_id
                codigo = product.barcode or product.default_code or ''

                ws.append([
                    order.name,
                    fecha,
                    cliente,
                    ruc,
                    telefono,
                    celular,
                    contacto,
                    direccion,
                    forma_pago,
                    codigo,
                    product.display_name or '',
                    line.name or '',
                    line.product_uom_qty,
                    line.price_unit,
                    line.price_subtotal,
                    '',
                ])

                # Foto del local: se incrusta una sola vez, en la primera
                # línea de cada orden, para no repetir la imagen por línea.
                if first_line_of_order and partner and partner.image_1920:
                    try:
                        import base64
                        img_bytes = base64.b64decode(partner.image_1920)
                        xl_img = XLImage(io.BytesIO(img_bytes))
                        xl_img.width = 90
                        xl_img.height = 90
                        ws.row_dimensions[row_idx].height = 68
                        ws.add_image(xl_img, "%s%s" % (get_column_letter(photo_col), row_idx))
                    except Exception:
                        pass
                first_line_of_order = False

        column_widths = [16, 12, 28, 14, 14, 14, 22, 32, 16, 18, 40, 32, 10, 14, 14, 14]
        for i, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.read()

    def _dianke_xlsx_filename(self):
        fecha = fields.Date.context_today(self)
        return "Pedidos Dianke %s.xlsx" % fecha.strftime('%d-%m-%Y')

    def _send_dianke_export_email(self):
        """Envía por correo el XLSX consolidado de self (órdenes de venta
        confirmadas) a Dianke y marca cada orden como exportada."""
        orders = self.filtered(lambda o: o.state == 'sale')
        if not orders:
            return False

        xlsx_bytes = orders._generate_dianke_xlsx_bytes()
        filename = orders._dianke_xlsx_filename()

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'raw': xlsx_bytes,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'sale.order',
            'res_id': orders[0].id,
        })

        subject = "Pedidos confirmados para Dianke - %s" % orders._dianke_xlsx_filename().replace('.xlsx', '')
        body = """
<div style="margin: 0px; padding: 0px;">
    <p style="margin: 0px; padding: 0px; font-size: 13px;">
        Buenas noches,
        <br/><br/>
        Adjunto el Excel con los pedidos confirmados (<strong>%s</strong>) listos para subir al sistema.
        <br/><br/>
        Saludos,<br/>
        Shalom Panamá.
        <br/><br/>
    </p>
</div>
""" % ", ".join(orders.mapped('name'))

        mail = self.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_to': DIANKE_EMAIL_TO,
            'attachment_ids': [(6, 0, [attachment.id])],
            'model': 'sale.order',
            'res_id': orders[0].id,
        })
        mail.send()

        orders.write({
            'custom_dianke_exported': True,
            'custom_dianke_exported_date': fields.Datetime.now(),
        })
        return True

    def action_send_dianke_export_now(self):
        """Botón/acción manual: envía a Dianke las órdenes seleccionadas que
        estén confirmadas (ignora las que no estén en estado 'sale')."""
        orders = self.filtered(lambda o: o.state == 'sale')
        if not orders:
            from odoo.exceptions import UserError
            raise UserError("Selecciona al menos una orden de venta CONFIRMADA para enviar a Dianke.")
        orders._send_dianke_export_email()
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def _cron_send_dianke_export(self):
        """Job automático (11:59pm): junta todas las órdenes de venta
        confirmadas que aún no se le han mandado a Dianke y las envía en un
        solo correo con un solo Excel."""
        pending = self.search([
            ('state', '=', 'sale'),
            ('custom_dianke_exported', '=', False),
        ])
        if pending:
            pending._send_dianke_export_email()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    custom_product_image = fields.Binary(
        related='product_id.image_1024',
        string='Imagen',
        readonly=True,
    )
    custom_product_barcode = fields.Char(
        related='product_id.barcode',
        string='Código de Barras',
        readonly=True,
    )
    custom_product_default_code = fields.Char(
        related='product_id.default_code',
        string='Código',
        readonly=True,
    )
    custom_promo_status = fields.Char(
        string='Promo',
        compute='_compute_custom_promo_status',
    )

    def _price_qualifies_for_promo(self, line, rule):
        """Verifica si el precio de la línea califica para la promoción."""
        product = line.product_id
        price = line.price_unit

        # Tintes NNP: precio mínimo especial 1.16
        is_tinte_nnp = False
        if rule.product_category_id:
            cat = product.categ_id
            while cat:
                if cat.name and 'tinte' in cat.name.lower() and 'nnp' in cat.name.lower():
                    is_tinte_nnp = True
                    break
                cat = cat.parent_id
        if not is_tinte_nnp and product in rule.product_ids:
            # Verificar por nombre si es tinte NNP
            if 'TINTE NNP' in (product.name or '').upper():
                is_tinte_nnp = True

        if is_tinte_nnp:
            return price >= TINTE_NNP_MIN_PRICE

        # Todos los demás: precio no puede bajar del list_price
        list_price = product.list_price or 0.0
        if list_price <= 0:
            return True
        return price >= list_price - 0.001  # tolerancia de redondeo

    def _get_matched_program(self, line, programs):
        """Retorna (program, rule) que aplica a esta línea, o (None, None)."""
        for program in programs:
            for rule in program.rule_ids:
                if line.product_id in rule.product_ids:
                    return program, rule
                if rule.product_category_id:
                    cat = line.product_id.categ_id
                    while cat:
                        if cat == rule.product_category_id:
                            return program, rule
                        cat = cat.parent_id
        return None, None

    @api.depends(
        'product_id', 'product_uom_qty', 'price_unit',
        'order_id.order_line.product_id',
        'order_id.order_line.product_uom_qty',
        'order_id.order_line.price_unit',
    )
    def _compute_custom_promo_status(self):
        programs = self.env['loyalty.program'].search([
            ('program_type', '=', 'buy_x_get_y'),
            ('active', '=', True),
        ])

        for line in self:
            if not line.product_id or line.display_type:
                line.custom_promo_status = ''
                continue

            program, rule = self._get_matched_program(line, programs)

            if not program or not rule:
                line.custom_promo_status = ''
                continue

            # Verificar precio de esta línea
            if not self._price_qualifies_for_promo(line, rule):
                line.custom_promo_status = ''
                continue

            # Sumar qty de todas las líneas que califican al mismo programa
            total_qty = 0.0
            for ol in line.order_id.order_line:
                if ol.display_type or not ol.product_id:
                    continue
                _, ol_rule = self._get_matched_program(ol, programs)
                if ol_rule != rule:
                    continue
                if not self._price_qualifies_for_promo(ol, rule):
                    continue
                total_qty += ol.product_uom_qty

            min_qty = rule.minimum_qty
            reward = program.reward_ids[:1]
            reward_qty = int(reward.reward_product_qty) if reward else 0
            promo_label = f'{int(min_qty)}+{reward_qty}'

            if min_qty <= 0:
                line.custom_promo_status = ''
                continue

            promos_completas = int(total_qty // min_qty)
            remainder = total_qty % min_qty

            if remainder == 0 and total_qty >= min_qty:
                line.custom_promo_status = f'✅ Tienes {promos_completas} promos completas · Llevas {int(total_qty)} unidades válidas'
            else:
                faltan = int(min_qty - remainder) if remainder > 0 else int(min_qty)
                line.custom_promo_status = f'⏳ Faltan {faltan} unidades · Llevas {int(total_qty)} unidades válidas'
