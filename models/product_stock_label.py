import pytz

from odoo import api, fields, models

PARAM_NEVADA_WH_CODE = 'stock_picking_sale_buttons.nevada_warehouse_code'
PARAM_NEVADA_STALE_DAYS = 'stock_picking_sale_buttons.nevada_stale_days'
PARAM_NEVADA_LIST_DATE = 'stock_picking_sale_buttons.nevada_list_date'
DEFAULT_NEVADA_WH_CODE = 'ALBRK'  # "Bodega Greenpeak" de la empresa NEVADA ZONA UNO
DEFAULT_NEVADA_STALE_DAYS = 7


class ProductProduct(models.Model):
    """Texto corto de existencias para las tarjetas del catálogo de Ventas.

    Usa lo DISPONIBLE (`free_qty` = en bodega menos lo ya reservado), no lo que hay en bodega: así el
    vendedor sabe de un vistazo si le queda o no. Se arma aquí (y no en la vista) para mostrar cifras
    enteras y un texto corto que quepa en una línea, también en celular.

    Dianke y Nevada NUNCA se mezclan: los vendedores trabajan con las dos empresas activas y Odoo, en
    ese caso, suma las bodegas de ambas en `free_qty`/`qty_available`. Por eso lo "disponible" se calcula
    solo con las bodegas de Dianke (todas menos la de Nevada) y lo de Nevada va aparte, como un dato
    informativo (su lista semanal) que se muestra en la esquina de la foto."""
    _inherit = 'product.product'

    dk_stock_label = fields.Char(compute='_compute_dk_stock_label')
    dk_stock_tone = fields.Char(compute='_compute_dk_stock_label')   # danger | warning | success
    dk_stock_extra = fields.Char(compute='_compute_dk_stock_label')  # "13 reservados"

    dk_nevada_qty = fields.Float(compute='_compute_dk_nevada', string='Nevada (lista semanal)')
    dk_nevada_label = fields.Char(compute='_compute_dk_nevada')  # "Nevada: 500" (vacío si no hay)
    dk_nevada_tone = fields.Char(compute='_compute_dk_nevada')   # fresh | old (lista de más de 7 días)
    dk_nevada_tip = fields.Char(compute='_compute_dk_nevada')    # texto largo (tooltip)

    @staticmethod
    def _dk_fmt_qty(qty):
        qty = round(qty or 0.0, 2)
        if float(qty).is_integer():
            return '%d' % qty
        return ('%.2f' % qty).rstrip('0').rstrip('.')

    # ------------------------------------------------------------------ bodegas
    @api.model
    def _dk_nevada_warehouse(self):
        """Bodega de Nevada (la que solo guarda su lista semanal). Se busca por código; el código se puede
        cambiar con el parámetro del sistema `stock_picking_sale_buttons.nevada_warehouse_code`."""
        code = self.env['ir.config_parameter'].sudo().get_param(PARAM_NEVADA_WH_CODE, DEFAULT_NEVADA_WH_CODE)
        return self.env['stock.warehouse'].sudo().with_context(active_test=False).search(
            [('code', '=', code)], limit=1)

    @api.model
    def _dk_own_warehouses(self):
        """Bodegas de Dianke visibles para el usuario: todas menos la de Nevada."""
        nevada = self._dk_nevada_warehouse()
        domain = [('id', '!=', nevada.id)] if nevada else []
        return self.env['stock.warehouse'].search(domain)

    def _dk_own_stock(self):
        """{id del producto: (disponible, en bodega)} contando solo las bodegas de Dianke."""
        warehouses = self._dk_own_warehouses()
        if not warehouses:
            return {p.id: (p.free_qty, p.qty_available) for p in self}
        result = {p.id: [0.0, 0.0] for p in self}
        for warehouse in warehouses:
            for product in self.with_context(warehouse_id=warehouse.id):
                result[product.id][0] += product.free_qty
                result[product.id][1] += product.qty_available
        return {pid: tuple(vals) for pid, vals in result.items()}

    # ------------------------------------------------------------------ Dianke
    @api.depends('is_storable', 'free_qty', 'qty_available')
    @api.depends_context('allowed_company_ids')
    def _compute_dk_stock_label(self):
        own_stock = self._dk_own_stock()
        for product in self:
            if not product.is_storable:
                product.dk_stock_label = ''
                product.dk_stock_tone = ''
                product.dk_stock_extra = ''
                continue
            free, on_hand = own_stock.get(product.id, (0.0, 0.0))
            if free <= 0:
                label, tone = 'Sin existencia', 'danger'
            elif free <= 5:
                label, tone = 'Quedan %s' % product._dk_fmt_qty(free), 'warning'
            else:
                label, tone = 'Disponible: %s' % product._dk_fmt_qty(free), 'success'
            reserved = on_hand - free
            product.dk_stock_label = label
            product.dk_stock_tone = tone
            product.dk_stock_extra = (
                '%s reservados' % product._dk_fmt_qty(reserved) if on_hand > 0 and reserved > 0.0001 else ''
            )

    # ------------------------------------------------------------------ Nevada
    @api.model
    def _dk_nevada_list_date(self, warehouse):
        """Fecha de la última lista de Nevada: la que dejó el botón "Cargar lista de Nevada" o, si se cargó
        con el Inventario físico de Odoo, la última vez que se tocó una existencia de su bodega."""
        dates = []
        param = self.env['ir.config_parameter'].sudo().get_param(PARAM_NEVADA_LIST_DATE)
        if param:
            dates.append(fields.Datetime.to_datetime(param))
        quant = self.env['stock.quant'].sudo().search(
            [('location_id', 'child_of', warehouse.view_location_id.id)], order='write_date desc', limit=1)
        if quant and quant.write_date:
            dates.append(quant.write_date)
        return max(dates) if dates else False

    @api.depends('is_storable')
    @api.depends_context('allowed_company_ids')
    def _compute_dk_nevada(self):
        warehouse = self._dk_nevada_warehouse()
        quantities = {}
        list_date = False
        if warehouse and self.ids:
            groups = self.env['stock.quant'].sudo()._read_group(
                [('product_id', 'in', self.ids),
                 ('location_id', 'child_of', warehouse.view_location_id.id),
                 ('location_id.usage', '=', 'internal')],
                ['product_id'], ['quantity:sum'])
            quantities = {product.id: qty for product, qty in groups}
            if any(qty > 0 for qty in quantities.values()):
                list_date = self._dk_nevada_list_date(warehouse)
        stale_days = int(self.env['ir.config_parameter'].sudo().get_param(
            PARAM_NEVADA_STALE_DAYS, DEFAULT_NEVADA_STALE_DAYS) or DEFAULT_NEVADA_STALE_DAYS)
        days = (fields.Datetime.now() - list_date).days if list_date else 0
        panama = pytz.timezone('America/Panama')
        date_text = pytz.utc.localize(list_date).astimezone(panama).strftime('%d/%m/%Y') if list_date else ''
        if days <= 0:
            age_text = 'hoy'
        elif days == 1:
            age_text = 'hace 1 día'
        else:
            age_text = 'hace %d días' % days
        old = days > stale_days
        for product in self:
            qty = quantities.get(product.id, 0.0)
            product.dk_nevada_qty = qty
            if qty <= 0:
                product.dk_nevada_label = ''
                product.dk_nevada_tone = ''
                product.dk_nevada_tip = ''
                continue
            qty_text = product._dk_fmt_qty(qty)
            product.dk_nevada_tone = 'old' if old else 'fresh'
            product.dk_nevada_label = 'Nevada: %s%s' % (qty_text, ' · hace %d d' % days if old else '')
            product.dk_nevada_tip = (
                'Nevada Zona 1: %s u. según su lista del %s (%s). No es tuyo: puede venderse a otro antes. '
                'Confirma con Nevada.' % (qty_text, date_text, age_text))
