import base64
import csv
import io
import re
import unicodedata

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape

from .product_stock_label import PARAM_NEVADA_LIST_DATE

HEADER_BARCODE = ('barra', 'barcode', 'ean', 'codigo')
HEADER_QTY = ('cantidad', 'existencia', 'stock', 'inventario', 'disponible', 'qty', 'unidades')
MAX_LISTED = 30


def _plain(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return text.strip().lower()


def _norm_code(value):
    """Código de barras comparable: sin espacios, sin '.0' de Excel y sin ceros a la izquierda."""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = re.sub(r'\s+', '', str(value))
    if re.fullmatch(r'\d+\.0+', text):
        text = text.split('.')[0]
    return text.lstrip('0')


def _to_qty(value):
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(' ', '')
    if ',' in text and '.' not in text:
        text = text.replace(',', '.')
    else:
        text = text.replace(',', '')
    try:
        return float(text)
    except ValueError:
        return None


class DkNevadaStockWizard(models.TransientModel):
    """Carga la lista semanal de existencias que da Nevada en SU bodega (solo informativa).

    Nevada no se opera desde Odoo: esa bodega existe únicamente para que los vendedores vean, en el
    catálogo, cuánto dice Nevada que tiene. Cada semana se sube su Excel (código de barras + cantidad) y la
    bodega queda igual a esa lista. Primero se REVISA (no cambia nada) y recién después se aplica."""
    _name = 'dk.nevada.stock.wizard'
    _description = 'Cargar lista de existencias de Nevada'

    state = fields.Selection(
        [('draft', 'Subir archivo'), ('preview', 'Revisar'), ('done', 'Listo')], default='draft')
    file = fields.Binary(string='Lista de Nevada (Excel .xlsx o .csv)')
    filename = fields.Char()
    zero_missing = fields.Boolean(
        string='Poner en cero lo que Nevada no incluya en la lista', default=True,
        help='Los productos que tenían cantidad la semana pasada y ahora no vienen en el archivo quedan en 0.')
    summary = fields.Html(readonly=True, sanitize=False)

    # ------------------------------------------------------------------ lectura del archivo
    def _read_rows(self):
        """Filas del archivo como listas de celdas."""
        if not self.file:
            raise UserError('Sube primero el archivo de Nevada.')
        raw = base64.b64decode(self.file)
        name = (self.filename or '').lower()
        if name.endswith('.csv'):
            text = raw.decode('utf-8-sig', errors='replace')
            try:
                dialect = csv.Sniffer().sniff(text[:2000], delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            return [row for row in csv.reader(io.StringIO(text), dialect)]
        try:
            import openpyxl
            workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception as error:  # archivo dañado o de otro tipo
            raise UserError('No pude abrir el archivo. Debe ser un Excel .xlsx o un .csv (%s).' % error)
        sheet = workbook.worksheets[0]
        return [list(row) for row in sheet.iter_rows(values_only=True)]

    def _parse(self):
        """({código normalizado: cantidad}, filas sin cantidad válida, descripción de las columnas)."""
        rows = self._read_rows()
        col_code = col_qty = None
        header_index = -1
        for index, row in enumerate(rows[:15]):
            cells = [_plain(cell) for cell in row]
            code = next((i for key in HEADER_BARCODE for i, c in enumerate(cells) if key in c), None)
            qty = next((i for key in HEADER_QTY for i, c in enumerate(cells) if key in c), None)
            if code is not None and qty is not None and code != qty:
                col_code, col_qty, header_index = code, qty, index
                break
        if col_code is None:
            col_code, col_qty = 0, 1  # sin encabezado reconocible: columna A = código, columna B = cantidad
            description = 'sin encabezado reconocible: columna A = código de barras, columna B = cantidad'
        else:
            header = rows[header_index]
            description = 'código de barras = "%s", cantidad = "%s"' % (header[col_code], header[col_qty])
        quantities = {}
        skipped = 0
        for row in rows[header_index + 1:]:
            if not row or len(row) <= max(col_code, col_qty):
                continue
            code = _norm_code(row[col_code])
            if not code:
                continue
            qty = _to_qty(row[col_qty])
            if qty is None:
                skipped += 1
                continue
            quantities[code] = quantities.get(code, 0.0) + max(qty, 0.0)
        if not quantities:
            raise UserError('No encontré códigos de barras con cantidad en el archivo. Revisa que tenga una '
                            'columna de código de barras y otra de cantidad.')
        return quantities, skipped, description

    # ------------------------------------------------------------------ plan de cambios
    def _plan(self):
        """Calcula qué pasaría, sin tocar nada."""
        Product = self.env['product.product']
        warehouse = Product._dk_nevada_warehouse()
        if not warehouse:
            raise UserError('No encuentro la bodega de Nevada (código "ALBRK"). Revisa el parámetro '
                            '"stock_picking_sale_buttons.nevada_warehouse_code".')
        quantities, skipped, description = self._parse()

        by_code = {}
        ambiguous = set()
        products = Product.with_context(active_test=False).search([('barcode', '!=', False)])
        for product in products:
            by_code.setdefault(_norm_code(product.barcode), set()).add(product.id)
        for multi in self.env['product.barcode.multi'].search([]):
            by_code.setdefault(_norm_code(multi.name), set()).add(multi.product_id.id)

        target = {}          # id producto -> cantidad que dice Nevada
        not_found = []
        not_stored = []
        for code, qty in quantities.items():
            ids = by_code.get(code, set())
            if not ids:
                not_found.append(code)
                continue
            if len(ids) > 1:
                ambiguous.add(code)
                continue
            pid = next(iter(ids))
            target[pid] = target.get(pid, 0.0) + qty
        storable = {p.id for p in Product.browse(list(target)).filtered('is_storable')}
        for pid in list(target):
            if pid not in storable:
                not_stored.append(pid)
                del target[pid]

        location = warehouse.lot_stock_id
        quants = self.env['stock.quant'].sudo().search([('location_id', '=', location.id)])
        current = {}
        for quant in quants:
            current[quant.product_id.id] = current.get(quant.product_id.id, 0.0) + quant.quantity
        to_zero = []
        if self.zero_missing:
            to_zero = [pid for pid, qty in current.items() if qty != 0 and pid not in target]
        changes = [pid for pid, qty in target.items() if abs(current.get(pid, 0.0) - qty) > 1e-6]
        return {
            'warehouse': warehouse, 'location': location, 'description': description, 'skipped': skipped,
            'target': target, 'current': current, 'not_found': not_found, 'ambiguous': sorted(ambiguous),
            'not_stored': not_stored, 'to_zero': to_zero, 'changes': changes,
        }

    @staticmethod
    def _bullets(items):
        shown = ''.join('<li>%s</li>' % html_escape(i) for i in items[:MAX_LISTED])
        more = '<li>… y %d más</li>' % (len(items) - MAX_LISTED) if len(items) > MAX_LISTED else ''
        return '<ul>%s%s</ul>' % (shown, more)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new',
        }

    # ------------------------------------------------------------------ botones
    def action_preview(self):
        self.ensure_one()
        plan = self._plan()
        Product = self.env['product.product'].with_context(active_test=False)
        parts = [
            '<p>Columnas leídas: %s.</p>' % html_escape(plan['description']),
            '<ul>'
            '<li><b>%d</b> productos de la lista encontrados en Odoo.</li>'
            '<li><b>%d</b> cambian de cantidad (los demás ya estaban igual).</li>'
            '<li><b>%d</b> quedarán en cero porque Nevada ya no los lista.</li>'
            '</ul>' % (len(plan['target']), len(plan['changes']), len(plan['to_zero'])),
        ]
        if plan['not_found']:
            parts.append('<p class="text-warning"><b>%d códigos del archivo no existen en Odoo</b> (se ignoran):</p>%s'
                         % (len(plan['not_found']), self._bullets(plan['not_found'])))
        if plan['ambiguous']:
            parts.append('<p class="text-warning"><b>%d códigos están en más de un producto</b> (se ignoran):</p>%s'
                         % (len(plan['ambiguous']), self._bullets(plan['ambiguous'])))
        if plan['not_stored']:
            names = [p.display_name for p in Product.browse(plan['not_stored'])]
            parts.append('<p class="text-warning"><b>%d productos no manejan inventario</b> (se ignoran):</p>%s'
                         % (len(names), self._bullets(names)))
        if plan['skipped']:
            parts.append('<p class="text-warning">%d filas sin una cantidad válida se ignoraron.</p>' % plan['skipped'])
        if plan['to_zero']:
            names = [p.display_name for p in Product.browse(plan['to_zero'])]
            parts.append('<p>Quedarán en cero:</p>%s' % self._bullets(names))
        parts.append('<p class="text-muted">Todavía no se cambió nada. Si todo se ve bien, pulsa '
                     '<b>Aplicar en la bodega de Nevada</b>.</p>')
        self.write({'state': 'preview', 'summary': ''.join(parts)})
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        self.write({'state': 'draft', 'summary': False})
        return self._reopen()

    def action_apply(self):
        self.ensure_one()
        plan = self._plan()
        warehouse, location = plan['warehouse'], plan['location']
        company = warehouse.company_id
        Quant = self.env['stock.quant'].sudo().with_company(company).with_context(
            allowed_company_ids=(company | self.env.company).ids,
            inventory_mode=True,
            inventory_name='Lista semanal de Nevada %s' % fields.Date.context_today(self),
        )
        existing = {}
        for quant in Quant.search([('location_id', '=', location.id)]):
            existing[quant.product_id.id] = existing.get(quant.product_id.id, Quant.browse()) | quant

        to_apply = Quant.browse()
        updated = 0
        for pid in plan['changes']:
            quants = existing.get(pid)
            if quants:
                first = quants[:1]
                first.inventory_quantity = plan['target'][pid]
                to_apply |= first
                for extra in quants[1:]:  # si hubiera varias líneas del mismo producto, el resto queda en 0
                    extra.inventory_quantity = 0
                    to_apply |= extra
            else:
                to_apply |= Quant.create({
                    'product_id': pid, 'location_id': location.id,
                    'inventory_quantity': plan['target'][pid],
                })
            updated += 1
        zeroed = 0
        for pid in plan['to_zero']:
            for quant in existing.get(pid, Quant.browse()):
                quant.inventory_quantity = 0
                to_apply |= quant
            zeroed += 1
        if to_apply:
            result = to_apply.action_apply_inventory()
            if isinstance(result, dict):
                raise UserError('Odoo pide confirmar algo antes de aplicar (por ejemplo, un producto con '
                                'seguimiento por lote). No se cambió nada.')
        self.env['ir.config_parameter'].sudo().set_param(PARAM_NEVADA_LIST_DATE, fields.Datetime.to_string(fields.Datetime.now()))
        self.write({
            'state': 'done',
            'summary': '<p><b>Listo.</b> %d productos actualizados y %d puestos en cero en la bodega de Nevada. '
                       'Los vendedores ya ven la lista nueva en el catálogo.</p>' % (updated, zeroed),
        })
        return self._reopen()
