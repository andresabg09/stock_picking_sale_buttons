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

    def _dianke_order_rows_data(self):
        """Arma, para cada orden de self, un dict con todos los datos ya
        resueltos (cliente, líneas, etc.) para no repetir esta lógica entre
        la hoja plana y la hoja resumen."""
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
                'lines': order.order_line.filtered(lambda l: not l.display_type),
            })
        return data

    def _generate_dianke_xlsx_bytes(self):
        """Genera un único XLSX con 2 pestañas para todas las órdenes de
        self:
        1) "Importar": una fila por línea de producto, todo repetido — para
           que un sistema externo la importe de forma automática y plana.
        2) "Resumen": un bloque por orden (los datos del cliente aparecen
           una sola vez, con la foto del local) y debajo la tabla de sus
           productos — para que una persona lo revise fácil."""
        from openpyxl import Workbook
        import io

        wb = Workbook()
        rows_data = self._dianke_order_rows_data()

        ws_import = wb.active
        ws_import.title = "Importar"
        self._fill_dianke_import_sheet(ws_import, rows_data)

        ws_resumen = wb.create_sheet("Resumen")
        self._fill_dianke_resumen_sheet(ws_resumen, rows_data)

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

    def _fill_dianke_import_sheet(self, ws, rows_data):
        """Hoja 1 "Importar": plana, una fila por línea de producto, con
        solo las columnas que Andrés pidió (el resto — fecha, RUC, teléfono,
        celular, forma de pago — queda solo en "Resumen"). Orden, Cliente,
        Contacto y Dirección se repiten en TODAS las líneas del pedido (no
        solo en la primera) — así el sistema que importe el archivo puede
        identificar en cada fila, sin ambigüedad, a qué cliente pertenece
        cada producto. Las filas con una nota extra (cambio, gratis, etc.)
        se resaltan en rosa salmón pastel."""
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter

        CURRENCY_FORMAT = '#,##0.00'
        NOTA_FILL = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid")

        headers = [
            "Orden de Venta", "Cliente", "Contacto", "Dirección",
            "Código/Referencia", "Código Anclado", "Producto",
            "Descripción / Notas", "Cantidad", "Precio Unitario", "Subtotal",
        ]
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        for data in rows_data:
            fijos = [data['order'].name, data['local'], data['contacto'], data['direccion']]
            for line in data['lines']:
                product = line.product_id
                codigo = product.barcode or product.default_code or ''
                codigo_anclado = self._dianke_codigo_anclado(product)
                nota = self._dianke_extra_note(product.display_name, line.name)

                ws.append(fijos + [
                    codigo,
                    codigo_anclado,
                    product.display_name or '',
                    nota,
                    line.product_uom_qty,
                    line.price_unit,
                    line.price_subtotal,
                ])
                row = ws.max_row
                ws.cell(row=row, column=10).number_format = CURRENCY_FORMAT
                ws.cell(row=row, column=11).number_format = CURRENCY_FORMAT

                if nota:
                    for col in range(1, len(headers) + 1):
                        ws.cell(row=row, column=col).fill = NOTA_FILL

        column_widths = [16, 28, 18, 32, 18, 22, 40, 26, 10, 14, 14]
        for i, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width
        ws.freeze_panes = "A2"

    def _fill_dianke_resumen_sheet(self, ws, rows_data):
        """Hoja 2 "Resumen": un bloque por orden — cabecera del cliente una
        sola vez (con foto) y debajo la tabla de sus productos, con total."""
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        ITEM_COLS = 6  # Código, Código Anclado, Producto/Descripción, Cantidad, Precio, Subtotal
        PHOTO_COL = ITEM_COLS + 1
        CURRENCY_FORMAT = '$#,##0.00'

        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        item_header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        total_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        thin_border = Border(*(Side(style='thin', color='BFBFBF'),) * 4)

        column_widths = [18, 22, 46, 10, 13, 13, 14]
        for i, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width

        row_idx = 0
        for data in rows_data:
            order = data['order']

            # --- Bloque de cabecera del pedido (3 filas, fusionadas) ---
            header_start_row = row_idx + 1
            linea1 = "%s · %s · %s · RUC %s" % (order.name, data['fecha'], data['local'], data['ruc'] or 'N/A')
            linea2 = "Tel/Cel: %s / %s · Contacto: %s · Forma de Pago: %s" % (
                data['telefono'] or 'N/A', data['celular'] or 'N/A',
                data['contacto'] or 'N/A', data['forma_pago'] or 'N/A',
            )
            linea3 = "Dirección: %s" % (data['direccion'] or 'N/A')

            for texto in (linea1, linea2, linea3):
                row_idx += 1
                ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=ITEM_COLS)
                cell = ws.cell(row=row_idx, column=1, value=texto)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(vertical='center')
                ws.row_dimensions[row_idx].height = 18

            self._dianke_embed_partner_photo(
                ws, data['partner'],
                "%s%s" % (get_column_letter(PHOTO_COL), header_start_row),
                header_start_row,
            )

            # --- Encabezado de la tabla de productos ---
            row_idx += 1
            item_header_row = row_idx
            for col, texto in enumerate(
                ["Código", "Código Anclado", "Producto / Descripción", "Cantidad", "Precio Unit.", "Subtotal"],
                start=1,
            ):
                cell = ws.cell(row=item_header_row, column=col, value=texto)
                cell.font = Font(bold=True)
                cell.fill = item_header_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')

            # --- Líneas de producto ---
            total_pedido = 0.0
            for line in data['lines']:
                row_idx += 1
                product = line.product_id
                codigo = product.barcode or product.default_code or ''
                codigo_anclado = self._dianke_codigo_anclado(product)
                nota = self._dianke_extra_note(product.display_name, line.name)
                descripcion = product.display_name or ''
                if nota:
                    descripcion = "%s — %s" % (descripcion, nota)
                total_pedido += line.price_subtotal

                valores = [codigo, codigo_anclado, descripcion, line.product_uom_qty, line.price_unit, line.price_subtotal]
                for col, valor in enumerate(valores, start=1):
                    cell = ws.cell(row=row_idx, column=col, value=valor)
                    cell.border = thin_border
                    if col in (5, 6):
                        cell.number_format = CURRENCY_FORMAT
                    if col in (4, 5, 6):
                        cell.alignment = Alignment(horizontal='right')
                    else:
                        cell.alignment = Alignment(horizontal='left', wrap_text=True)

            # --- Fila de total del pedido ---
            row_idx += 1
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=ITEM_COLS - 1)
            cell = ws.cell(row=row_idx, column=1, value="Total del pedido")
            cell.font = Font(bold=True)
            cell.fill = total_fill
            cell.alignment = Alignment(horizontal='right')
            cell.border = thin_border
            total_cell = ws.cell(row=row_idx, column=ITEM_COLS, value=total_pedido)
            total_cell.font = Font(bold=True)
            total_cell.fill = total_fill
            total_cell.border = thin_border
            total_cell.number_format = CURRENCY_FORMAT
            total_cell.alignment = Alignment(horizontal='right')

            # --- Fila en blanco de separación entre pedidos ---
            row_idx += 1

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
        Adjunto el Excel con los pedidos confirmados (<strong>%s</strong>). Tiene 2 pestañas: <strong>"Importar"</strong> (formato plano, lista para subir directo al sistema) y <strong>"Resumen"</strong> (vista más fácil de leer, con foto del local por pedido).
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
        Adjunto el Excel con los pedidos confirmados (<strong>%s</strong>). Tiene 2 pestañas: <strong>"Importar"</strong> (formato plano, lista para subir directo al sistema) y <strong>"Resumen"</strong> (vista más fácil de leer, con foto del local por pedido).
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
