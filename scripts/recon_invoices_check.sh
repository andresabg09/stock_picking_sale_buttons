#!/bin/bash
# recon_invoices_check.sh — Solo lectura. NO crea ni modifica nada.
# El wizard de "Traer precios pactados de facturas" no encontró nada
# para un cliente (id=1369, LA PAGODA DE MAÑANITA) que SÍ muestra un
# botón "Facturado: 19,613.18 B/." en su ficha. Este script revisa:
#   1) qué hay detrás de ese campo "Facturado" (puede ser un campo de
#      Studio, no el estándar de Odoo).
#   2) cuántas facturas de cliente (account.move, out_invoice) existen
#      de verdad para ese partner_id exacto, en qué estado, y si el
#      partner_id de esas facturas es distinto (ej. una dirección hija).
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
PARTNER_ID = 1369  # LA PAGODA DE MAÑANITA, según la URL de la captura

partner = env['res.partner'].browse(PARTNER_ID)
print(f"Cliente: {partner.display_name!r} (id={partner.id}, "
      f"commercial_partner_id={partner.commercial_partner_id.id})")

print("\n========== CAMPOS DE res.partner CON 'factur' EN EL NOMBRE ==========")
for fname, field in partner._fields.items():
    if 'factur' in fname.lower() or 'invoic' in fname.lower():
        try:
            valor = getattr(partner, fname)
        except Exception as e:
            valor = f"(error leyendo: {e})"
        print(f"  {fname} | tipo={field.type} | string={field.string!r} | valor={valor}")

print("\n========== account.move (TODOS los tipos/estados) para este partner_id exacto ==========")
moves = env['account.move'].search([('partner_id', '=', PARTNER_ID)])
print(f"Total: {len(moves)}")
for m in moves[:20]:
    print(f"  id={m.id} | name={m.name!r} | move_type={m.move_type} | state={m.state} | "
          f"amount_total={m.amount_total} | partner_id={m.partner_id.id}")

print("\n========== account.move con commercial_partner_id de este cliente ==========")
moves2 = env['account.move'].search([('commercial_partner_id', '=', partner.commercial_partner_id.id)])
print(f"Total: {len(moves2)}")
partner_ids_distintos = set(moves2.mapped('partner_id').ids)
print(f"partner_id distintos entre esas facturas: {partner_ids_distintos}")
for m in moves2[:20]:
    print(f"  id={m.id} | name={m.name!r} | move_type={m.move_type} | state={m.state} | "
          f"amount_total={m.amount_total} | partner_id={m.partner_id.id} ({m.partner_id.display_name!r})")

print("\n========== Líneas de producto en esas facturas (si las hay, posted+out_invoice) ==========")
lines = env['account.move.line'].search([
    ('move_id.commercial_partner_id', '=', partner.commercial_partner_id.id),
    ('move_id.move_type', '=', 'out_invoice'),
    ('move_id.state', '=', 'posted'),
    ('product_id', '!=', False),
    ('display_type', '=', False),
])
print(f"Total líneas de producto encontradas: {len(lines)}")
for l in lines[:15]:
    print(f"  move={l.move_id.name!r} | producto={l.product_id.display_name!r} | "
          f"price_unit={l.price_unit} | partner_id_de_la_factura={l.move_id.partner_id.id}")

print("\n========== FIN ==========")
PYEOF
