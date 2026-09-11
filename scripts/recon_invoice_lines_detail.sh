#!/bin/bash
# recon_invoice_lines_detail.sh — Solo lectura. NO crea ni modifica nada.
# La factura INV/2026/00586 (id=1125, LA PAGODA DE MAÑANITA, $1,218.46)
# no tiene ninguna línea con product_id — este script imprime TODAS sus
# líneas tal cual están (sin filtrar por producto/display_type) para
# ver qué hay de verdad ahí, y revisa si viene de un pedido de Punto de
# Venta (pos.order) en vez de una orden de venta normal.
# Correr por SSH y pegar TODA la salida.

set -e

CID=$(docker ps --filter "name=crm_odoo." --format "{{.Names}}" | head -n1)
if [ -z "$CID" ]; then
  echo "No se encontró el contenedor crm_odoo. Revisa 'docker ps'."
  exit 1
fi
echo "== Contenedor detectado: $CID =="

DB_HOST=$(docker exec "$CID" printenv HOST)
DB_PORT=$(docker exec "$CID" printenv PORT)
DB_USER=$(docker exec "$CID" printenv USER)
DB_PASS=$(docker exec "$CID" printenv PASSWORD)

docker exec -i "$CID" odoo shell -d shalom --no-http \
  --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASS" <<'PYEOF'
MOVE_ID = 1125  # INV/2026/00586

move = env['account.move'].browse(MOVE_ID)
print(f"Factura: {move.name!r} | move_type={move.move_type} | state={move.state} | "
      f"amount_total={move.amount_total} | invoice_origin={move.invoice_origin!r}")

print("\n========== TODAS las líneas de esta factura (sin filtrar nada) ==========")
for l in move.line_ids:
    print(f"  id={l.id} | name={l.name!r} | display_type={l.display_type!r} | "
          f"product_id={l.product_id.id if l.product_id else False} | "
          f"account_id={l.account_id.display_name!r} | price_unit={l.price_unit} | "
          f"quantity={l.quantity} | debit={l.debit} | credit={l.credit}")

print("\n========== ¿Viene de un pedido de Punto de Venta? ==========")
print(f"invoice_origin apunta a: {move.invoice_origin!r}")
pos_orders = env['pos.order'].search([('account_move', '=', MOVE_ID)]) if 'pos.order' in env else env['pos.order']
print(f"pos.order con account_move={MOVE_ID}: {len(pos_orders)} -> {pos_orders.mapped('name')}")

print("\n========== Todos los módulos 'point_of_sale' instalados? ==========")
pos_module = env['ir.module.module'].search([('name', '=', 'point_of_sale')])
print(f"point_of_sale state: {pos_module.state if pos_module else 'NO EXISTE EL MODULO'}")

print("\n========== ¿Existe alguna sale.order.line con el mismo producto real vendido a este cliente? ==========")
partner_id = move.partner_id.id
so_lines = env['sale.order.line'].search([
    ('order_id.partner_id', '=', partner_id),
    ('order_id.state', '=', 'sale'),
    ('product_id', '!=', False),
    ('display_type', '=', False),
], limit=10)
print(f"Total sale.order.line encontradas (muestra hasta 10): {len(so_lines)}")
for sol in so_lines:
    print(f"  orden={sol.order_id.name!r} | producto={sol.product_id.display_name!r} | "
          f"price_unit={sol.price_unit} | qty={sol.product_uom_qty}")

print("\n========== FIN ==========")
PYEOF
