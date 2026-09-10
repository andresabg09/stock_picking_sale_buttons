#!/bin/bash
# recon_stock_check2.sh — Solo lectura. NO crea ni modifica nada.
# Casi todo lo que se había elegido (por ser lo más vendido en 180 días)
# resultó tener qty_available = 0 ahora mismo. Este recon busca, dentro
# de cada categoría (Tinte NNP, Aliset, Cera/Wokali) y también el
# decolorante, qué SKUs sí tienen stock real hoy, para rediseñar las 7
# ventas solo con productos que de verdad hay. Correr por SSH y pegar
# TODA la salida.

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
Product = env['product.product']

def con_stock(termino, min_qty=0.01, limit=200):
    # qty_available es un campo computado NO almacenado — no se puede usar
    # en 'order' de search() (Odoo 18 lo rechaza: "Cannot convert ... to
    # SQL because it is not stored"). Se trae todo por nombre y se ordena
    # en Python después de calcular qty_available.
    print(f"\n--- '{termino}' CON STOCK (qty_available > 0) ---")
    productos = Product.search([('name', 'ilike', termino)], limit=limit)
    con_stock_list = [p for p in productos if p.qty_available > min_qty]
    con_stock_list.sort(key=lambda p: p.qty_available, reverse=True)
    if not con_stock_list:
        print("  (NINGUNO con stock)")
    for p in con_stock_list:
        print(f"  id={p.id} | {p.display_name!r} | qty_available={p.qty_available} | "
              f"precio_lista={p.list_price} | sale_ok={p.sale_ok}")

print("\n========== TINTE NNP CON STOCK ==========")
con_stock("TINTE NNP")

print("\n\n========== ALISET CON STOCK ==========")
con_stock("ALISET")

print("\n\n========== CERA / WOKALI CON STOCK ==========")
con_stock("CERA")
con_stock("WOKALI")

print("\n\n========== DECOLORANTE (con o sin stock, incluyendo archivados) ==========")
productos = env['product.product'].with_context(active_test=False).search(
    [('name', 'ilike', 'decolorante')], limit=20
)
if not productos:
    print("  (no existe ningún producto con 'decolorante' en el nombre)")
for p in productos:
    print(f"  id={p.id} | {p.display_name!r} | qty_available={p.qty_available} | "
          f"precio_lista={p.list_price} | sale_ok={p.sale_ok} | activo={p.active}")

print("\n\n========== OXIGENTA CON STOCK (ya se sabía, se confirma) ==========")
con_stock("OXIGENTA")

print("\n\n========== FIN RECON STOCK 2 ==========")
PYEOF
