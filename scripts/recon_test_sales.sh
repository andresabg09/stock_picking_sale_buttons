#!/bin/bash
# recon_test_sales.sh — Solo lectura. NO crea ni modifica nada.
# Busca los clientes de la ruta B pedidos para las 7 ventas de prueba y
# lista los productos más vendidos (con precio actual) para poder armar
# líneas realistas. Correr por SSH en la VM y pegar TODA la salida en el chat.

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
import re

print("\n========== CLIENTES BUSCADOS (ruta B) ==========")
buscar = [
    "buena suerte",
    "marketing angy",
    "multi pollo alex",
    "surtimax",
    "tommy",
    "chavez 2",
    "poderoso net",
]

Partner = env['res.partner']
for termino in buscar:
    print(f"\n--- Buscando: '{termino}' ---")
    partners = Partner.search([('name', 'ilike', termino), ('customer_rank', '>', 0)], limit=10)
    if not partners:
        partners = Partner.search([('name', 'ilike', termino)], limit=10)
    if not partners:
        print("  (sin coincidencias)")
    for p in partners:
        ruta = ""
        try:
            fsm_loc = env['fsm.location'].search([('partner_id', '=', p.id)], limit=1)
            if fsm_loc and fsm_loc.fsm_route_id:
                ruta = fsm_loc.fsm_route_id.name
        except Exception as e:
            ruta = f"(error consultando ruta: {e})"
        contacto = getattr(p, 'x_nombre_contacto', '') or ''
        print(f"  id={p.id} | name={p.name!r} | ruta={ruta!r} | contacto={contacto!r} | "
              f"ciudad={p.city!r} | telefono={p.phone or p.mobile!r}")

print("\n\n========== PRODUCTOS MAS VENDIDOS (ultimos 180 dias, ventas confirmadas) ==========")
env.cr.execute("""
    SELECT sol.product_id, SUM(sol.product_uom_qty) AS qty, SUM(sol.price_subtotal) AS total
    FROM sale_order_line sol
    JOIN sale_order so ON so.id = sol.order_id
    WHERE so.state = 'sale'
      AND so.date_order >= (NOW() - INTERVAL '180 days')
      AND sol.product_id IS NOT NULL
      AND sol.display_type IS NULL
    GROUP BY sol.product_id
    ORDER BY qty DESC
    LIMIT 30
""")
rows = env.cr.fetchall()
Product = env['product.product']
for product_id, qty, total in rows:
    prod = Product.browse(product_id)
    print(f"  id={product_id} | {prod.display_name!r} | vendidos={qty} | precio_lista={prod.list_price} | "
          f"total_vendido_180d={round(total, 2)}")

print("\n\n========== FIN RECON ==========")
PYEOF
