import json
import unicodedata

from odoo import models, fields, api

# Palabras (sin tildes) que, en una línea a $0, la vuelven regalo de promoción. "regalo" a propósito NO está.
DK_PROMO_WORDS = ('gratis', 'promo', 'regalia')
PARAM_FAST_LINE_ONCHANGE = 'stock_picking_sale_buttons.fast_line_onchange'
# Campos de una línea que se pueden cambiar sin recalcular el traslado completo (cantidad, "Listo", etc.)
DK_LIGHT_LINE_FIELDS = {'quantity', 'custom_ready', 'picked', 'description_picking', 'forecast_availability'}


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    invoice_count = fields.Integer(
        string='Pedidos',
        compute='_compute_invoice_count',
    )

    # ------------------------------------------------------------------
    # Aviso de promociones al despachar (pedido de Andrés 2026-11-13)
    # Mismo programa y misma regla de precio que la columna Promo de Ventas.
    #  - Cuentan las unidades PAGADAS (Cantidad) de las filas con "Listo" marcado = ya están en la caja.
    #  - El regalo NO necesita "Listo": en su línea sale siempre cuánto se puede dar con lo que va en la caja.
    #  - REGALO = línea de recompensa de Odoo, o línea a $0 cuya descripción diga "gratis", "promo(ción)" o
    #    "regalía" (NO "regalo": puede ser un obsequio al cliente que no es promoción).
    #  - Las pagadas que dejan la promo incompleta llevan un punto naranja.
    # Los avisos viajan en UN campo del traslado (JSON {id_de_línea: texto}) y una pieza de pantalla
    # (`dk_promo_note.js`) los dibuja en cada línea. Devolverlos como cambios de las líneas hacía que, al marcar
    # varios "Listo" rápido, una respuesta atrasada del servidor volviera a encender/apagar filas.
    # ------------------------------------------------------------------
    custom_promo_json = fields.Char(
        string='Avisos de promoción',
        compute='_compute_custom_promo_json',
    )

    @api.depends(
        'move_ids_without_package.quantity',
        'move_ids_without_package.custom_ready',
        'move_ids_without_package.product_id',
        'move_ids_without_package.description_picking',
    )
    def _compute_custom_promo_json(self):
        for picking in self:
            picking.custom_promo_json = picking._dk_promo_json()

    def _dk_promo_json(self, overrides=None):
        self.ensure_one()
        notes = {mid: txt for mid, txt in self._dk_promo_notes(overrides).items() if txt}
        return json.dumps(notes) if notes else False

    @staticmethod
    def _dk_norm_text(text):
        text = unicodedata.normalize('NFD', (text or '').lower())
        return ''.join(c for c in text if unicodedata.category(c) != 'Mn')

    @classmethod
    def _dk_is_promo_gift_line(cls, move):
        """True si la línea es regalo de promoción (ver arriba)."""
        sline = move.sale_line_id
        if not sline:
            return False
        if sline.is_reward_line:
            return True
        if sline.price_unit or sline.discount < 100:
            return False
        text = cls._dk_norm_text('%s %s' % (move.description_picking or '', sline.name or ''))
        return any(word in text for word in DK_PROMO_WORDS)

    @staticmethod
    def _dk_promo_text(paid, gift, paid_pending, x, y):
        """Texto del aviso del regalo. paid = pagadas con Listo, gift = regalo en las líneas, x+y = promo X+Y."""
        promos, rem = divmod(paid, x)
        allowed = promos * y
        if paid_pending:
            # todavía faltan pagadas por marcar: solo se informa el tope actual, sin alarma
            return '🕒 Van %d pagadas → regalo máx. %d (hay %d)' % (paid, allowed, gift)
        if gift > allowed:
            return '⚠️ Van %d pagadas = %d promo. Regalo máx. %d, hay %d → quita %d' % (
                paid, promos, allowed, gift, gift - allowed)
        if gift < allowed:
            return '⏳ Van %d pagadas → regalo máx. %d (hay %d, faltan %d)' % (paid, allowed, gift, allowed - gift)
        txt = '✅ Van %d pagadas → regalo %d' % (paid, allowed)
        if rem:
            txt += ' · faltan %d para otro' % (x - rem)
        return txt

    def _dk_promo_notes(self, overrides=None):
        """{id_de_línea: texto} para las líneas con orden de venta. `overrides` = {id: {'quantity','custom_ready'}}
        con cambios que el formulario todavía no guardó."""
        self.ensure_one()
        overrides = overrides or {}
        moves = self.move_ids_without_package.filtered(lambda m: m.sale_line_id and m.product_id and m.id)
        notes = {m.id: '' for m in moves}
        if not moves:
            return notes
        programs = self.env['loyalty.program'].search([
            ('program_type', '=', 'buy_x_get_y'), ('active', '=', True),
        ])
        if not programs:
            return notes
        SOL = self.env['sale.order.line']
        data = {}

        def entry(program):
            return data.setdefault(program.id, {
                'program': program, 'rule': False, 'paid': 0.0, 'gift': 0.0, 'paid_pending': False,
                'paid_moves': [], 'gift_moves': []})

        for move in moves:
            sline = move.sale_line_id
            vals = overrides.get(move.id, {})
            qty = vals.get('quantity', move.quantity) or 0.0
            if self._dk_is_promo_gift_line(move):
                program = sline.reward_id.program_id if sline.is_reward_line else SOL._get_matched_program(
                    sline, programs)[0]
                if not program or program not in programs:
                    continue
                d = entry(program)
                d['gift_moves'].append(move.id)
                d['gift'] += qty
            else:
                program, rule = SOL._get_matched_program(sline, programs)
                if not program or not SOL._price_qualifies_for_promo(sline, rule):
                    continue
                d = entry(program)
                d['rule'] = d['rule'] or rule
                d['paid_moves'].append(move.id)
                if vals.get('custom_ready', move.custom_ready):
                    d['paid'] += qty
                else:
                    d['paid_pending'] = True
        for d in data.values():
            rule = d['rule'] or d['program'].rule_ids[:1]
            if not rule or rule.minimum_qty <= 0:
                continue
            x = int(rule.minimum_qty)
            reward = d['program'].reward_ids[:1]
            y = int(reward.reward_product_qty) if reward else 0
            paid, gift = int(d['paid']), int(d['gift'])
            txt = self._dk_promo_text(paid, gift, d['paid_pending'], x, y)
            for mid in d['gift_moves']:
                notes[mid] = txt
            if d['paid_moves'] and not d['paid_pending'] and paid % x:
                for mid in d['paid_moves']:
                    notes[mid] = '🟠'
        return notes

    def onchange(self, values, field_names, fields_spec):
        """Traslados grandes (100+ líneas): cada vez que se cambia la cantidad o se marca "Listo" en UNA línea,
        el formulario le pide a Odoo recalcular el traslado COMPLETO (todas las líneas, disponibilidad, estado...)
        y eso tardaba ~2,5 s con 134 líneas, por cada línea. Si lo único que cambió son campos simples de líneas
        ya existentes, no hay nada que recalcular en el traslado: lo de la línea ya lo calculó la propia línea y
        el resto se actualiza al guardar. Apagar con el parámetro del sistema
        `stock_picking_sale_buttons.fast_line_onchange` = 0."""
        if self._dk_is_light_line_edit(values, field_names):
            result = {'value': {}}
            if len(self) == 1 and self.id:
                overrides = {c[1]: c[2] for c in (values.get('move_ids_without_package') or [])}
                result['value']['custom_promo_json'] = self._dk_promo_json(overrides) or False
            return result
        return super().onchange(values, field_names, fields_spec)

    def _dk_is_light_line_edit(self, values, field_names):
        if list(field_names or []) != ['move_ids_without_package']:
            return False
        if self.env['ir.config_parameter'].sudo().get_param(PARAM_FAST_LINE_ONCHANGE, '1') in ('0', 'False', 'false'):
            return False
        commands = (values or {}).get('move_ids_without_package') or []
        if not commands:
            return False
        for command in commands:
            # (1, id, {campos}) = actualizar una línea que ya existe
            if len(command) != 3 or command[0] != 1 or not isinstance(command[2], dict):
                return False
            if not set(command[2]) <= DK_LIGHT_LINE_FIELDS:
                return False
        return True

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_id:
            return {}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    @api.depends('sale_id')
    def _compute_invoice_count(self):
        for picking in self:
            if picking.sale_id:
                picking.invoice_count = len(picking.sale_id.invoice_ids)
            else:
                picking.invoice_count = 0
    def action_view_invoices(self):
        self.ensure_one()
        if not self.sale_id:
            return {}
        invoices = self.sale_id.invoice_ids
        if len(invoices) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': invoices.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('id', 'in', invoices.ids)],
        }

class StockMove(models.Model):
    _inherit = 'stock.move'
    custom_product_image = fields.Binary(
        related='product_id.image_256',
        string='Imagen',
        readonly=True,
    )
    custom_product_barcode = fields.Char(
        related='product_id.barcode',
        string='Código de Barras',
        readonly=True,
    )
    custom_ready = fields.Boolean(
        string='Listo',
        default=False,
    )

    custom_promo_note = fields.Char(
        string='Promo',
        compute='_compute_custom_promo_note',
    )

    def _compute_custom_promo_note(self):
        # Marcador: el texto real sale de `stock.picking.custom_promo_json` (lo dibuja dk_promo_note.js).
        for move in self:
            move.custom_promo_note = False

    # Producto con Cantidad menor que la Demanda (0 o parcial) y con unidades en la lista de Nevada (Zona 1): la fila
    # se sombrea de naranja suave para que bodega sepa que puede estar por llegar (pedido de Andrés 2026-11-13).
    dk_nevada_wait = fields.Boolean(compute='_compute_dk_nevada_wait')

    @api.depends('quantity', 'product_uom_qty', 'state', 'product_id')
    def _compute_dk_nevada_wait(self):
        for move in self:
            move.dk_nevada_wait = bool(
                move.product_id
                and move.state not in ('done', 'cancel', 'draft')
                and (move.quantity or 0.0) < (move.product_uom_qty or 0.0) - 0.001
                and move.product_id.dk_nevada_qty > 0
            )

    def _sync_description_from_sale(self):
        for move in self:
            if move.sale_line_id:
                sale_name = move.sale_line_id.name or ''
                product_name = move.product_id.name or ''
                if sale_name.strip() and sale_name.strip() != product_name.strip():
                    move.description_picking = sale_name
                else:
                    move.description_picking = False

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._sync_description_from_sale()
        return moves

    def write(self, vals):
        result = super().write(vals)
        # Si se asigna o cambia la línea de venta, sincronizar descripción
        if 'sale_line_id' in vals:
            self._sync_description_from_sale()
        return result
