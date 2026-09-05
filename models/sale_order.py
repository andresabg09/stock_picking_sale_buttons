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
        """Devuelve (nombre_local, ruc, telefono, celular, nombre_contacto,
        direccion) para el reporte de Dianke, a partir de campos de
        res.partner: los estándar de Odoo (vat, phone, mobile) más el campo
        de Studio `x_nombre_contacto` (nombre de la persona, ej. "Julio";
        confirmado por Andrés 2026-09-05 — separado de `name`, que es el
        nombre del local/negocio)."""
        if not partner:
            return ('', '', '', '', '', '')

        company = partner.commercial_partner_id or partner
        nombre_contacto = getattr(partner, 'x_nombre_contacto', '') or ''

        # Se arma solo con los campos de dirección (calle, ciudad, provincia,
        # país) — sin el nombre del cliente, que campos como
        # contact_address_complete traen pegado al inicio.
        partes_direccion = [
            partner.street,
            partner.street2,
            partner.city,
            partner.state_id.name if partner.state_id else '',
            partner.country_id.name if partner.country_id else '',
        ]
        direccion = ", ".join(p for p in partes_direccion if p)

        return (
            partner.name or '',
            partner.vat or company.vat or '',
            partner.phone or company.phone or '',
            partner.mobile or company.mobile or '',
            nombre_contacto,
            direccion,
        )

    def _dianke_route_name(self, partner):
        """Nombre de la ruta del cliente (fsm.route), buscando el
        fsm.location cuyo partner_id es este cliente — confirmado por
        Andrés 2026-09-05. Vacío si no se encuentra o el módulo de rutas
        no está instalado (no debe tumbar el export por esto)."""
        if not partner:
            return ''
        try:
            location = self.env['fsm.location'].search([('partner_id', '=', partner.id)], limit=1)
            return location.fsm_route_id.name if location and location.fsm_route_id else ''
        except Exception:
            return ''

    @staticmethod
    def _dianke_delivery_date(order_date):
        """4 días hábiles (lunes a viernes, sin contar sábado ni domingo)
        desde la fecha de la orden — regla confirmada por Andrés
        2026-09-05. No contempla feriados, solo fines de semana. No hay
        ningún campo en el sistema que ya calcule esto, así que se computa
        aquí mismo, sin guardar nada nuevo en la orden."""
        if not order_date:
            return None
        from datetime import timedelta
        d = order_date.date() if hasattr(order_date, 'date') else order_date
        dias_habiles = 0
        while dias_habiles < 4:
            d = d + timedelta(days=1)
            if d.weekday() < 5:  # 0=lunes ... 4=viernes (5=sábado, 6=domingo se saltan)
                dias_habiles += 1
        return d

    @staticmethod
    def _dianke_payment_checkboxes(payment_method):
        """Traduce custom_payment_method a las casillas de la plantilla de
        Dianke (Efectivo/Tarjeta/ACH). Transferencia se marca como ACH (es
        pago electrónico). Yappy y Crédito no tienen casilla propia en su
        plantilla, así que se agrega una 4ta opción "Otro: <forma de pago>"
        para no perder esa información — pedido de Andrés 2026-09-05."""
        efectivo = payment_method == 'efectivo'
        tarjeta = payment_method == 'tarjeta'
        ach = payment_method == 'transferencia'
        otro_label = None
        if payment_method and not (efectivo or tarjeta or ach):
            otro_label = dict(PAYMENT_METHOD_SELECTION).get(payment_method, payment_method)
        return efectivo, tarjeta, ach, otro_label

    def _dianke_order_rows_data(self):
        """Arma, para cada orden de self, un dict con todos los datos ya
        resueltos (cliente, ruta, fecha de entrega, líneas, etc.)."""
        payment_labels = dict(PAYMENT_METHOD_SELECTION)
        data = []
        for order in self.sorted(key=lambda o: o.name):
            partner = order.partner_id
            local, ruc, telefono, celular, contacto, direccion = self._dianke_contact_info(partner)
            data.append({
                'order': order,
                'partner': partner,
                'local': local,
                'ruc': ruc,
                'telefono': telefono,
                'celular': celular,
                'contacto': contacto,
                'direccion': direccion,
                'forma_pago': payment_labels.get(order.custom_payment_method, order.custom_payment_method or ''),
                'fecha': order.date_order.strftime('%d/%m/%Y') if order.date_order else '',
                'ruta': self._dianke_route_name(partner),
                'fecha_entrega': self._dianke_delivery_date(order.date_order),
                'lines': order.order_line.filtered(lambda l: not l.display_type),
            })
        return data

    def _generate_dianke_xlsx_bytes(self):
        """Genera un único XLSX, en el formato oficial de pedidos de Dianke
        (plantilla compartida por Andrés 2026-09-05), repetido en un bloque
        por cada orden de self."""
        from openpyxl import Workbook
        import io

        wb = Workbook()
        rows_data = self._dianke_order_rows_data()

        ws = wb.active
        ws.title = "Pedido Dianke"
        self._fill_dianke_template_sheet(ws, rows_data)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def _dianke_embed_partner_photo(ws, partner, anchor_cell, row_for_height, height=90):
        """Incrusta la foto del contacto (si tiene) en anchor_cell. Devuelve
        True si se incrustó algo."""
        if not partner or not partner.image_1920:
            return False
        from openpyxl.drawing.image import Image as XLImage
        import base64
        import io
        try:
            img_bytes = base64.b64decode(partner.image_1920)
            xl_img = XLImage(io.BytesIO(img_bytes))
            xl_img.width = height
            xl_img.height = height
            ws.row_dimensions[row_for_height].height = max(
                ws.row_dimensions[row_for_height].height or 0, height * 0.75
            )
            ws.add_image(xl_img, anchor_cell)
            return True
        except Exception:
            return False

    def _dianke_codigo_anclado(self, product):
        """Códigos de barras alternos/anclados del producto (mismo patrón
        que ya se usa en el Excel de compras a proveedores)."""
        additional = self.env['product.barcode.multi'].search([('product_id', '=', product.id)])
        return ", ".join(additional.mapped('name')) if additional else ''

    @staticmethod
    def _dianke_extra_note(display_name, line_name):
        """Devuelve solo la parte de line_name (la descripción/nota que
        escribió el vendedor) que NO es el nombre del producto — ej. si
        line_name es "ALISET NNP 69GR CAMBIO X CAMBIO" y display_name es
        "ALISET NNP 69GR", devuelve "CAMBIO X CAMBIO". Si line_name es
        igual al nombre del producto (o no aporta nada nuevo), devuelve
        cadena vacía en vez de repetir el nombre completo."""
        display_name = (display_name or '').strip()
        line_name = (line_name or '').strip()
        if not line_name:
            return ''
        if not display_name:
            return line_name

        idx = line_name.upper().find(display_name.upper())
        if idx == -1:
            # No hay traslape: el texto es completamente distinto al
            # nombre del producto, se conserva tal cual.
            return line_name

        remainder = line_name[:idx] + line_name[idx + len(display_name):]
        return remainder.strip(' -—.,')

    def _fill_dianke_template_sheet(self, ws, rows_data):
        """Hoja única con el formato oficial de pedidos de Dianke (plantilla
        "Formato_para_recibir_pedidos_clientes.xlsx" que Andrés compartió
        2026-09-05), repetido en un bloque por cada orden de rows_data. Se
        agregan 2 datos que la plantilla de Dianke no trae pero Andrés
        pidió de todas formas: RUC y foto del local (esta última fuera de
        las columnas A-E, para no romper el formato de ellos)."""
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter

        N_COLS = 5  # A-E, igual que la plantilla de Dianke
        PHOTO_COL = N_COLS + 2

        LABEL_FONT = Font(bold=True, size=10, color="173B4D")
        VALUE_FILL = PatternFill(start_color="FFF9E8", end_color="FFF9E8", fill_type="solid")
        DIVIDER_FILL = PatternFill(start_color="E8F1F5", end_color="E8F1F5", fill_type="solid")
        SECTION_FILL = PatternFill(start_color="173B4D", end_color="173B4D", fill_type="solid")
        SECTION_FONT = Font(bold=True, size=10, color="FFFFFF")
        TABLE_HEADER_FILL = PatternFill(start_color="2F6F7E", end_color="2F6F7E", fill_type="solid")
        TABLE_HEADER_FONT = Font(bold=True, size=10, color="FFFFFF")
        ROW_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        NOTA_FILL = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid")

        column_widths = {1: 39.78, 2: 20, 3: 14, 4: 14, 5: 16, PHOTO_COL: 16}
        for col, width in column_widths.items():
            ws.column_dimensions[get_column_letter(col)].width = width

        row_idx = 0
        for data in rows_data:
            order = data['order']
            block_start_row = row_idx + 1
            entrega = data['fecha_entrega']
            entrega_str = entrega.strftime('%d/%m/%Y') if entrega else ''
            efectivo, tarjeta, ach, otro_label = self._dianke_payment_checkboxes(order.custom_payment_method)

            # --- Campos del pedido (etiqueta en A, valor fusionado B:E) ---
            campos = [
                ("Fecha", data['fecha']),
                ("Nombre o razón social del negocio", data['local']),
                ("RUC", data['ruc']),
                ("Nombre del contacto o persona que recibe el pedido", data['contacto']),
                ("Dirección exacta con indicaciones claras", data['direccion']),
                ("Teléfono de quien recibe el pedido", data['telefono'] or data['celular']),
                ("Número de ruta", data['ruta']),
                ("Número de pedido", order.name),
                ("Fecha en que se debe entregar el pedido al cliente", entrega_str),
            ]
            for label, valor in campos:
                row_idx += 1
                ws.cell(row=row_idx, column=1, value=label).font = LABEL_FONT
                ws.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=N_COLS)
                for col in range(2, N_COLS + 1):
                    cell = ws.cell(row=row_idx, column=col)
                    cell.fill = VALUE_FILL
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                ws.cell(row=row_idx, column=2, value=valor)
                ws.row_dimensions[row_idx].height = 24

            # --- Tipo de pago (casillas) ---
            row_idx += 1
            ws.cell(row=row_idx, column=1, value="Tipo de pago").font = LABEL_FONT
            opciones_pago = [("Efectivo", efectivo), ("Tarjeta", tarjeta), ("ACH", ach)]
            if otro_label:
                opciones_pago.append((otro_label, True))
            for i in range(N_COLS - 1):
                col = 2 + i
                cell = ws.cell(row=row_idx, column=col)
                cell.fill = VALUE_FILL
                if i < len(opciones_pago):
                    texto, marcado = opciones_pago[i]
                    cell.value = "%s %s" % ("☑" if marcado else "☐", texto)
                    cell.font = Font(bold=True, size=11)
                cell.alignment = Alignment(horizontal='center')
            ws.row_dimensions[row_idx].height = 24

            # --- Foto del local (a un lado, fuera de las columnas de la plantilla) ---
            self._dianke_embed_partner_photo(
                ws, data['partner'],
                "%s%s" % (get_column_letter(PHOTO_COL), block_start_row),
                block_start_row, height=110,
            )

            # --- Fila divisoria ---
            row_idx += 1
            for col in range(1, N_COLS + 1):
                ws.cell(row=row_idx, column=col).fill = DIVIDER_FILL if col == 1 else VALUE_FILL
            ws.row_dimensions[row_idx].height = 10

            # --- DETALLE DEL PEDIDO ---
            row_idx += 1
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=N_COLS)
            cell = ws.cell(row=row_idx, column=1, value="DETALLE DEL PEDIDO")
            cell.fill = SECTION_FILL
            cell.font = SECTION_FONT
            cell.alignment = Alignment(horizontal='center')
            ws.row_dimensions[row_idx].height = 22

            # --- Encabezado de la tabla de productos ---
            row_idx += 1
            for col, texto in enumerate(["Código", "Descripción", "Cantidad", "Precio venta", "Tipo de venta"], start=1):
                cell = ws.cell(row=row_idx, column=col, value=texto)
                cell.fill = TABLE_HEADER_FILL
                cell.font = TABLE_HEADER_FONT
                cell.alignment = Alignment(horizontal='center')
            ws.row_dimensions[row_idx].height = 22

            # --- Líneas de producto ---
            for line in data['lines']:
                row_idx += 1
                product = line.product_id
                codigo = product.barcode or product.default_code or ''
                nota = self._dianke_extra_note(product.display_name, line.name)
                tipo_venta = nota if nota else "Normal"

                valores = [codigo, product.display_name or '', line.product_uom_qty, line.price_unit, tipo_venta]
                for col, valor in enumerate(valores, start=1):
                    cell = ws.cell(row=row_idx, column=col, value=valor)
                    cell.fill = NOTA_FILL if nota else ROW_FILL
                    cell.alignment = Alignment(
                        horizontal='left' if col == 2 else 'center',
                        wrap_text=(col == 2),
                    )
                ws.row_dimensions[row_idx].height = 20

            # --- Separación entre pedidos ---
            row_idx += 2

        ws.freeze_panes = None

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
        Adjunto el Excel con los pedidos confirmados (<strong>%s</strong>), en el formato de pedido acordado con Dianke, listo para su revisión e importación al sistema.
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
        """Botón/acción manual: genera el Excel de las órdenes seleccionadas
        que estén confirmadas (ignora las que no estén en estado 'sale') y
        abre la ventana de confirmación para revisar/editar antes de enviar."""
        orders = self.filtered(lambda o: o.state == 'sale')
        if not orders:
            from odoo.exceptions import UserError
            raise UserError("Selecciona al menos una orden de venta CONFIRMADA para enviar a Dianke.")

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

        subject = "Pedidos confirmados para Dianke - %s" % filename.replace('.xlsx', '')
        body = """
<div style="margin: 0px; padding: 0px;">
    <p style="margin: 0px; padding: 0px; font-size: 13px;">
        Buenas noches,
        <br/><br/>
        Adjunto el Excel con los pedidos confirmados (<strong>%s</strong>), en el formato de pedido acordado con Dianke, listo para su revisión e importación al sistema.
        <br/><br/>
        Saludos,<br/>
        Shalom Panamá.
        <br/><br/>
    </p>
</div>
""" % ", ".join(orders.mapped('name'))

        wizard = self.env['sale.dianke.email.wizard'].create({
            'sale_order_ids': [(6, 0, orders.ids)],
            'email_to': DIANKE_EMAIL_TO,
            'subject': subject,
            'body': body,
            'attachment_ids': [(6, 0, [attachment.id])],
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.dianke.email.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

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
