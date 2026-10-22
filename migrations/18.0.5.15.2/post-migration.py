"""Encabezado de la tienda: el 2026-10-12 se cambió el logo desde el editor del sitio y Odoo guardó una COPIA propia del
encabezado para el sitio (vista con `website_id`). Una copia así ya no recibe los cambios del módulo (por eso el botón
"Iniciar sesión" y la franja de aviso no salían). El logo "DIANKE GROUP." ahora viene en el propio módulo, así que se
borra la copia y el sitio vuelve a usar la vista del módulo. Solo toca esa vista."""


def migrate(cr, version):
    if not version:
        return
    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    copies = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', '=', 'stock_picking_sale_buttons.dkh_header'),
        ('website_id', '!=', False),
    ])
    if copies:
        copies.unlink()
