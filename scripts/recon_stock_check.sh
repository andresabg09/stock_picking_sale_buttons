#!/bin/bash
# recon_stock_check.sh — Solo lectura. NO crea ni modifica nada.
# Revisa stock real (qty_available) antes de corregir las 7 ventas de
# prueba: variantes de Trat-Skala Mais Cachos, decolorantes disponibles,
# y stock actual de los productos ya usados (Aliset, tintes, etc.).
# Correr por SSH en la VM y pegar TODA la salida en el chat.

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

def listar(termino):
    print(f"\n--- '{termino}' ---")
    productos = Product.search([('name', 'ilike', termino), ('sale_ok', '=', True)], limit=40)
    if not productos:
        print("  (sin coincidencias)")
    for p in productos:
        print(f"  id={p.id} | {p.display_name!r} | qty_available={p.qty_available} | "
              f"precio_lista={p.list_price} | activo={p.active}")

print("\n========== VARIANTES TRAT-SKALA / MAIS CACHOS ==========")
listar("cachos")
listar("trat-skala")
listar("trat skala")

print("\n\n========== DECOLORANTES DISPONIBLES ==========")
listar("decolorante")

print("\n\n========== STOCK ACTUAL DE PRODUCTOS YA USADOS ==========")
ids_usados = [
    3439,  # TINTE NNP 1.0 NEGRO NATURAL
    3456,  # TINTE NNP 6.35 CHOCOLATE
    3446,  # TINTE NNP 3.0 CASTANO OSCURO
    3450,  # TINTE NNP 5.0 CASTANO CLARO
    3460,  # TINTE NNP 7.3 RUBIO MEDIO DORADO
    3461,  # TINTE NNP 7.66 RUBIO MEDIO ROJIZO INTENSO
    3462,  # TINTE NNP 8.0 RUBIO CLARO
    3465,  # TINTE NNP 9.0 RUBIO MUY CLARO
    3458,  # TINTE NNP 7.0 RUBIO MEDIANO
    3457,  # TINTE NNP 6.66 RUBIO OSCURO ROJIZO PROFUNDO
    3443,  # TINTE NNP 10.0 RUBIO EXTRA CLARO
    2178,  # ALISET NNP KERATINA SUPER 69GR
    2177,  # ALISET NNP KERATINA REGULAR 69GR
    2976,  # OXIGENTA CREMA NNP 40VOL 90ML
    2974,  # OXIGENTA CREMA NNP 30VOL 90ML
    7253,  # CERA CAPILAR WOKALI 150GR SURTIDAS
    3614,  # TRAT-SKALA MAIS CACHOS 1000GR
]
for pid in ids_usados:
    p = Product.browse(pid)
    print(f"  id={pid} | {p.display_name!r} | qty_available={p.qty_available} | precio_lista={p.list_price}")

print("\n\n========== FIN RECON STOCK ==========")
PYEOF
