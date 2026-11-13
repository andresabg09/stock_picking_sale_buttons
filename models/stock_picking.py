from markupsafe import Markup, escape
from odoo import models, fields, api

PARAM_FAST_LINE_ONCHANGE = 'stock_picking_sale_buttons.fast_line_onchange'
# Campos de una línea que se pueden cambiar sin recalcular el traslado completo (cantidad, "Listo", etc.)
DK_LIGHT_LINE_FIELDS = {'quantity', 'custom_ready', 'picked', 'description_picking', 'forecast_availability'}


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    invoice_count = fields.Integer(
        string='Pedidos',
        compute='_compute_invoice_count',
    )
    custom_promo_summary = fields.Html(
        string='Promociones',
        compute='_compute_custom_promo_summary',
        sanitize=False,
    )

    # ------------------------------------------------------------------
    # Aviso de promociones al despachar (pedido de Andrés 2026-11-13)
    # Cuenta la CANTIDAD de las filas con "Listo" marcado (= ya está en la caja del cliente).
    # Mismos programas "compra X y llévate Y" y misma regla de precio que la columna Promo de Ventas.
    # ------------------------------------------------------------------
    @api.depends(
        'move_ids_without_package.quantity',
        'move_ids_without_package.custom_ready',
        'move_ids_without_package.product_id',
    )
    def _compute_custom_promo_summary(self):
        for picking in self:
            picking.custom_promo_summary = picking._dk_promo_summary_html()

    def _dk_promo_summary_html(self, overrides=None):
        """HTML con una línea corta por promoción. `overrides` = {id_de_línea: {'quantity':..,'custom_ready':..}}
        con cambios que el formulario todavía no guardó."""
        self.ensure_one()
        overrides = overrides or {}
        moves = self.move_ids_without_package.filtered(lambda m: m.sale_line_id and m.product_id)
        if not moves:
            return False
        programs = self.env['loyalty.program'].search([
            ('program_type', '=', 'buy_x_get_y'), ('active', '=', True),
        ])
        if not programs:
            return False
        SOL = self.env['sale.order.line']
        data = {}  # program.id -> dict
        for move in moves:
            sline = move.sale_line_id
            if sline.is_reward_line:
                program = sline.reward_id.program_id
                if program not in programs:
                    continue
                d = data.setdefault(program.id, {'program': program, 'paid': 0.0, 'gift': 0.0, 'pending': False})
                kind, rule = 'gift', None
            else:
                program, rule = SOL._get_matched_program(sline, programs)
                if not program or not SOL._price_qualifies_for_promo(sline, rule):
                    continue
                d = data.setdefault(program.id, {'program': program, 'paid': 0.0, 'gift': 0.0, 'pending': False})
                d['rule'] = rule
                kind = 'paid'
            vals = overrides.get(move.id, {})
            ready = vals.get('custom_ready', move.custom_ready)
            qty = vals.get('quantity', move.quantity)
            if not ready:
                d['pending'] = True
                continue
            d['paid' if kind == 'paid' else 'gift'] += qty or 0.0
        lines = []
        for d in data.values():
            rule = d.get('rule')
            if not rule or rule.minimum_qty <= 0:
                continue
            program = d['program']
            x = int(rule.minimum_qty)
            reward = program.reward_ids[:1]
            y = int(reward.reward_product_qty) if reward else 0
            paid, gift = int(d['paid']), int(d['gift'])
            promos, rem = divmod(paid, x)
            allowed = promos * y
            name = escape(program.name or 'Promo')
            if d['pending']:
                css, txt = 'text-muted', '🕒 %s: llevas %d pagadas y %d de regalo (faltan filas por marcar Listo)' % (name, paid, gift)
            elif gift > allowed:
                css = 'text-danger fw-bold'
                txt = '⚠️ %s: %d pagadas = %d promo(s). Regalo máx. %d, hay %d → quita %d' % (name, paid, promos, allowed, gift, gift - allowed)
            elif rem:
                css = 'text-warning fw-bold'
                txt = '⏳ %s: %d pagadas. Faltan %d para otra promo' % (name, paid, x - rem)
                if gift < allowed:
                    txt += ' · regalo %d de %d' % (gift, allowed)
            elif gift < allowed:
                css = 'text-warning fw-bold'
                txt = '⏳ %s: %d promo(s). Regalo %d de %d → faltan %d' % (name, promos, gift, allowed, allowed - gift)
            elif promos:
                css = 'text-success fw-bold'
                txt = '✅ %s: %d promo(s) completas · regalo %d' % (name, promos, gift)
            else:
                continue
            lines.append('<div class="%s">%s</div>' % (css, txt))
        return Markup(''.join(lines)) if lines else False

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
                summary = self._dk_promo_summary_html(overrides)
                result['value']['custom_promo_summary'] = summary or False
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
