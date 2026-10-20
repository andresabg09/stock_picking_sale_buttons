import math

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape

from .dkh_rules import rule_for


class DkRestock(models.TransientModel):
    """Compras > Por agotar: productos cuyo disponible llegó al mínimo (o bajó de él), con la cantidad sugerida
    para pedir al proveedor. Se arma al abrir la pantalla (no guarda nada de forma permanente) y de ahí se crea
    el pedido (borrador) con el botón "Pedir a proveedor".

    Disponible = en bodega + por llegar - comprometido, solo con las bodegas de Dianke (nunca Nevada).
    Sugerido = lo que falta para quedar en el mínimo DESPUÉS de cubrir lo ya vendido (mínimo - disponible),
    subido al múltiplo del producto (tintes NNP de 5 en 5, Aliset/decolorantes de 12, Pocket de 6)."""
    _name = 'dk.restock'
    _description = 'Productos por agotar'

    name = fields.Char(default='Por agotar', readonly=True)
    line_ids = fields.One2many('dk.restock.line', 'restock_id', string='Productos')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    selected_count = fields.Integer(compute='_compute_totals', string='Productos marcados')
    total_units = fields.Float(compute='_compute_totals', string='Unidades a pedir')
    total_amount = fields.Monetary(compute='_compute_totals', string='Total estimado (sin ITBMS)')

    @api.depends('line_ids.selected', 'line_ids.qty_to_order', 'line_ids.subtotal')
    def _compute_totals(self):
        for restock in self:
            chosen = restock.line_ids.filtered(lambda l: l.selected and l.qty_to_order > 0)
            restock.selected_count = len(chosen)
            restock.total_units = sum(chosen.mapped('qty_to_order'))
            restock.total_amount = sum(chosen.mapped('subtotal'))

    # ------------------------------------------------------------------ cálculo
    @api.model
    def _dk_step(self, product):
        """Múltiplo en que se compra el producto (1 si no tiene regla)."""
        template = product.product_tmpl_id
        return rule_for(template.name, template._dkh_is_tinte())[1]

    @api.model
    def _dk_lines_vals(self):
        """Valores de las líneas, sin crear nada: agotados primero, luego por agotar, cada grupo por nombre."""
        Product = self.env['product.product']
        warehouses = Product._dk_own_warehouses()
        company = warehouses[:1].company_id or self.env.company
        products = Product.with_company(company).search([('is_storable', '=', True), ('dk_min_qty', '>', 0)])
        forecast = products._dk_own_forecast()
        rows = []
        for product in products:
            data = forecast[product.id]
            minimum = product.dk_min_qty
            available = data['available']
            if available > minimum:
                continue
            deficit = minimum - available
            step = max(1, self._dk_step(product))
            suggested = math.ceil(deficit / step) * step if deficit > 0 else step
            if available < 0:
                note = '%s que debes + %s de mínimo' % (Product._dk_fmt_qty(-available), Product._dk_fmt_qty(minimum))
            elif deficit == 0:
                note = 'Está justo en el mínimo'
            else:
                note = ''
            if step > 1 and suggested != deficit:
                note = (note + ' · ' if note else '') + 'sube a múltiplo de %d' % step
            seller = product._select_seller(quantity=suggested or 1.0) or product.seller_ids[:1]
            rows.append({
                'product_id': product.id,
                'state': 'out' if available <= 0 else 'low',
                'on_hand': data['on_hand'], 'committed': data['outgoing'], 'incoming': data['incoming'],
                'available': available, 'min_qty': minimum,
                'suggested': suggested, 'qty_to_order': suggested, 'note': note,
                'vendor_id': seller.partner_id.id if seller else False,
                'unit_price': seller.price if seller else 0.0,
                'selected': True,
                '_name': product.display_name,
            })
        rows.sort(key=lambda r: (0 if r['state'] == 'out' else 1, r['_name']))
        for row in rows:
            del row['_name']
        return rows

    @api.model
    def dk_count(self):
        """Cuántos productos están por agotarse (para el botón del panel de Compras)."""
        return len(self._dk_lines_vals())

    @api.model
    def action_open(self):
        restock = self.create({'line_ids': [(0, 0, vals) for vals in self._dk_lines_vals()]})
        return {
            'type': 'ir.actions.act_window',
            'name': 'Por agotar',
            'res_model': self._name,
            'res_id': restock.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    # ------------------------------------------------------------------ pedir
    def action_order(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.selected and l.qty_to_order > 0)
        if not lines:
            raise UserError('Marca al menos un producto con una cantidad mayor que 0 en "A pedir".')
        missing = lines.filtered(lambda l: not l.vendor_id)
        if missing:
            raise UserError('Estos productos no tienen proveedor definido (pestaña Compras del producto):\n- %s'
                            % '\n- '.join(missing.mapped('product_id.display_name')))
        wizard = self.env['dk.restock.order.wizard'].create({'restock_id': self.id})
        return {
            'type': 'ir.actions.act_window', 'name': 'Crear pedido a proveedor',
            'res_model': wizard._name, 'res_id': wizard.id, 'view_mode': 'form', 'target': 'new',
        }


class DkRestockLine(models.TransientModel):
    _name = 'dk.restock.line'
    _description = 'Producto por agotar'
    _order = 'id'

    restock_id = fields.Many2one('dk.restock', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    image = fields.Binary(related='product_id.image_128', string='Foto')
    state = fields.Selection([('out', 'Agotado'), ('low', 'Por agotar')], string='Estado', readonly=True)
    on_hand = fields.Float(string='En bodega (existencia)', digits='Product Unit of Measure', readonly=True)
    committed = fields.Float(string='Comprometido', digits='Product Unit of Measure', readonly=True)
    incoming = fields.Float(string='Por llegar', digits='Product Unit of Measure', readonly=True)
    available = fields.Float(string='Disponible', digits='Product Unit of Measure', readonly=True)
    min_qty = fields.Float(string='Mínimo', digits='Product Unit of Measure', readonly=True)
    suggested = fields.Float(string='Sugerido', digits='Product Unit of Measure', readonly=True)
    qty_to_order = fields.Float(string='A pedir', digits='Product Unit of Measure')
    note = fields.Char(string='Nota', readonly=True)
    selected = fields.Boolean(string='Incluir', default=True)
    nevada_qty = fields.Float(related='product_id.dk_nevada_qty', string='Nevada tiene')
    nevada_label = fields.Char(related='product_id.dk_nevada_label', string='Nevada')
    nevada_tone = fields.Char(related='product_id.dk_nevada_tone')
    vendor_id = fields.Many2one('res.partner', string='Proveedor', readonly=True)
    currency_id = fields.Many2one(related='restock_id.currency_id')
    unit_price = fields.Monetary(string='Costo unitario', readonly=True)
    subtotal = fields.Monetary(compute='_compute_subtotal', string='Costo')

    @api.depends('qty_to_order', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty_to_order * line.unit_price


class DkRestockOrderWizard(models.TransientModel):
    """Pop-up de confirmación: resume lo marcado por proveedor y crea las solicitudes de cotización en BORRADOR
    (nada se confirma ni se envía solo; el envío por correo con Excel se hace luego desde el pedido)."""
    _name = 'dk.restock.order.wizard'
    _description = 'Crear pedido a proveedor desde Por agotar'

    restock_id = fields.Many2one('dk.restock', required=True, ondelete='cascade')
    note = fields.Char(string='Nota para el proveedor (opcional)')
    summary = fields.Html(compute='_compute_summary', sanitize=False)

    def _chosen_lines(self):
        return self.restock_id.line_ids.filtered(lambda l: l.selected and l.qty_to_order > 0)

    @api.depends('restock_id.line_ids.selected', 'restock_id.line_ids.qty_to_order')
    def _compute_summary(self):
        Product = self.env['product.product']
        for wizard in self:
            lines = wizard._chosen_lines()
            parts = ['<p><b>%d productos · %s unidades · %s</b> estimado, sin ITBMS.</p>' % (
                len(lines), Product._dk_fmt_qty(sum(lines.mapped('qty_to_order'))),
                '%s %.2f' % (wizard.restock_id.currency_id.symbol or '', sum(lines.mapped('subtotal'))))]
            for vendor in lines.mapped('vendor_id'):
                vendor_lines = lines.filtered(lambda l: l.vendor_id == vendor)
                rows = ''.join(
                    '<tr><td>%s</td><td class="text-end">%s u.</td><td class="text-end">%.2f</td></tr>' % (
                        html_escape(line.product_id.display_name), Product._dk_fmt_qty(line.qty_to_order), line.subtotal)
                    for line in vendor_lines)
                parts.append('<h5 class="mt-3">%s <small class="text-muted">· 1 solicitud de cotización en borrador'
                             '</small></h5><table class="table table-sm">%s</table>' % (html_escape(vendor.display_name), rows))
            parts.append('<p class="text-muted">Nada se confirma todavía: queda como borrador para que lo revises.</p>')
            wizard.summary = ''.join(parts)

    def action_create(self):
        self.ensure_one()
        lines = self._chosen_lines()
        if not lines:
            raise UserError('No hay productos marcados con cantidad para pedir.')
        warehouses = self.env['product.product']._dk_own_warehouses()
        company = warehouses[:1].company_id or self.env.company
        Order = self.env['purchase.order'].with_company(company)
        orders = Order
        for vendor in lines.mapped('vendor_id'):
            vendor_lines = lines.filtered(lambda l: l.vendor_id == vendor)
            vals = {
                'partner_id': vendor.id,
                'company_id': company.id,
                'origin': 'Por agotar',
                'order_line': [(0, 0, {'product_id': l.product_id.id, 'product_qty': l.qty_to_order})
                               for l in vendor_lines],
            }
            if self.note:
                vals['notes'] = self.note
            orders |= Order.create(vals)
        lines.write({'selected': False})
        action = {'type': 'ir.actions.act_window', 'res_model': 'purchase.order', 'target': 'current'}
        if len(orders) == 1:
            action.update({'view_mode': 'form', 'res_id': orders.id, 'views': [(False, 'form')]})
        else:
            action.update({'name': 'Solicitudes de cotización creadas', 'view_mode': 'list,form',
                           'domain': [('id', 'in', orders.ids)]})
        return action
