from odoo import models, fields, api

TINTE_NNP_MIN_PRICE = 1.16


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_first_product_image = fields.Binary(
        string='Imagen',
        compute='_compute_custom_first_product_image',
        readonly=True,
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
