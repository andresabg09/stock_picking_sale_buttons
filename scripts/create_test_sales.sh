#!/bin/bash
# create_test_sales.sh — Crea y CONFIRMA 7 órdenes de venta (sale.order,
# estado 'sale') de PRUEBA para los clientes de la ruta "9 - San
# Miguelito ruta B", con productos surtidos entre los más vendidos,
# sumando ~$1,100 en total. Todas en Efectivo, sin ITBMS, con fecha
# normal (sin fecha especial de entrega). NO genera facturas — eso
# queda para cuando Andrés decida facturarlas manualmente.
# OJO: al confirmarse, Odoo SÍ crea los traslados/entregas de Inventario
# correspondientes y reserva stock real de estos productos, como
# cualquier venta real. Si son solo de prueba, cancelar después las 7
# órdenes (o sus traslados) para liberar ese stock reservado.
# Pedido explícito de Andrés (2026-09-10) para probar el flujo de ventas.
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

REF = "PRUEBA-CLAUDE-2026-09-10"
NOTA = (
    "Orden de PRUEBA generada para probar el flujo de ventas (Claude Code, "
    "2026-09-10). No es un pedido real de un cliente — se puede eliminar "
    "sin afectar contabilidad ni inventario."
)

# (product_id, cantidad, precio_override_o_None, nota_extra_o_None)
# Reglas de negocio confirmadas por Andrés (2026-09-10) para que esta
# canasta sea realista:
#   - NUNCA poner decolorante (todas las presentaciones están
#     descontinuadas/archivadas — no es solo que "casi no hay").
#   - Aliset SIEMPRE en múltiplos de 12 (se pide por docena, no funciona
#     de otra forma).
#   - Tintes SIEMPRE en múltiplos de 5, EXCEPTO el Tinte Negro (NNP 1.0),
#     que es el único que se puede sacar del múltiplo de 5 porque se usa
#     para completar la promoción (y para los cambios).
#   - Exactamente 3 de los 7 clientes tienen un "cambio" (Tinte Negro a
#     $0 con la nota CAMBIO X CAMBIO); los otros 4 no tienen cambios.
#   - Exactamente 2 de los 7 clientes llevan dos docenas (24 unidades)
#     de tratamiento capilar, en variedades surtidas (no la misma que
#     otro cliente) — el resto lleva media docena de una variedad, para
#     que ningún pedido repita exactamente la misma canasta.
ORDERS = [
    (1247, "MINI MARKET LA BUENA SUERTE", [
        (3439, 22, None, None),   # TINTE NNP 1.0 NEGRO NATURAL (normal, no es cambio)
        (3456, 15, None, None),   # TINTE NNP 6.35 CHOCOLATE
        (3446, 15, None, None),   # TINTE NNP 3.0 CASTANO OSCURO
        (2178, 12, None, None),   # ALISET NNP KERATINA SUPER 69GR (docena)
        (2177, 12, None, None),   # ALISET NNP KERATINA REGULAR 69GR (docena)
        (2976, 24, None, None),   # OXIGENTA CREMA NNP 40VOL 90ML
        (7253, 12, None, None),   # CERA CAPILAR WOKALI 150GR SURTIDAS
        (3614, 6, None, None),    # TRAT-SKALA MAIS CACHOS 1000GR (media docena)
    ]),
    (1279, "MINI SUPER SHOP MARKETING ANGY", [
        (3439, 10, None, None),
        (3439, 5, 0.0, "CAMBIO X CAMBIO"),
        (3460, 10, None, None),   # TINTE NNP 7.3 RUBIO MEDIO DORADO
        (3462, 10, None, None),   # TINTE NNP 8.0 RUBIO CLARO
        (2178, 12, None, None),   # ALISET SUPER (docena)
        (2177, 12, None, None),   # ALISET REGULAR (docena)
        (2976, 12, None, None),   # OXIGENTA CREMA NNP 40VOL 90ML
        (7253, 6, None, None),
        (3590, 6, None, None),    # TRAT-SKALA KIDS MAIS CACHINHOS 1000GR (media docena)
    ]),
    (1283, "MULTI POLLO ALEX", [
        (3439, 18, None, None),   # normal, no es cambio
        (3457, 10, None, None),   # TINTE NNP 6.66 RUBIO OSCURO ROJIZO PROFUNDO
        (2178, 12, None, None),   # ALISET SUPER (docena)
        (2177, 12, None, None),   # ALISET REGULAR (docena)
        (2974, 12, None, None),   # OXIGENTA CREMA NNP 30VOL 90ML
        (7253, 10, None, None),
        (3614, 12, None, None),   # TRAT-SKALA MAIS CACHOS 1000GR — docena 1 de 2
        (8813, 12, None, None),   # TRAT-SKALA MELANCIA 1000GR — docena 2 de 2 (surtido)
    ]),
    (1304, "MINI SUPER SURTIMAX", [
        (3439, 24, None, None),   # normal, no es cambio
        (3446, 15, None, None),   # TINTE NNP 3.0 CASTANO OSCURO
        (3450, 15, None, None),   # TINTE NNP 5.0 CASTANO CLARO
        (2178, 12, None, None),   # ALISET SUPER (docena)
        (2177, 12, None, None),   # ALISET REGULAR (docena)
        (2976, 24, None, None),   # OXIGENTA CREMA NNP 40VOL 90ML
        (7253, 12, None, None),
        (3612, 6, None, None),    # TRAT-SKALA KIDS 1000GR (media docena)
    ]),
    (2266, "MINI SUPER TOMMY", [
        (3439, 15, None, None),
        (3439, 5, 0.0, "CAMBIO X CAMBIO"),
        (3461, 10, None, None),   # TINTE NNP 7.66 RUBIO MEDIO ROJIZO INTENSO
        (2178, 12, None, None),   # ALISET SUPER (docena) — este cliente no lleva Regular
        (2976, 12, None, None),   # OXIGENTA CREMA NNP 40VOL 90ML
        (7253, 10, None, None),
        (3593, 6, None, None),    # TRAT-SKALA POTAO DE AMOR 18 ELEMENTOS 1000GR (media docena)
    ]),
    (1224, "MINI SUPER CHAVEZ 2", [
        (3439, 12, None, None),   # normal, no es cambio
        (3462, 10, None, None),   # TINTE NNP 8.0 RUBIO CLARO
        (3465, 10, None, None),   # TINTE NNP 9.0 RUBIO MUY CLARO
        (2178, 12, None, None),   # ALISET SUPER (docena)
        (2177, 12, None, None),   # ALISET REGULAR (docena)
        (2974, 12, None, None),   # OXIGENTA CREMA NNP 30VOL 90ML
        (7253, 10, None, None),
        (3606, 12, None, None),   # TRAT-SKALA DIVINO POTAO 1000GR — docena 1 de 2
        (3609, 12, None, None),   # TRAT-SKALA HIDRONUTRITIVO ALOE VERA 1000GR — docena 2 de 2
    ]),
    (1237, "PODEROSO NET", [
        (3439, 10, None, None),
        (3439, 5, 0.0, "CAMBIO X CAMBIO"),
        (3443, 10, None, None),   # TINTE NNP 10.0 RUBIO EXTRA CLARO
        (2177, 12, None, None),   # ALISET REGULAR (docena) — este cliente no lleva Super
        (2974, 12, None, None),   # OXIGENTA CREMA NNP 30VOL 90ML
        (7253, 10, None, None),
        (8813, 6, None, None),    # TRAT-SKALA MELANCIA 1000GR (media docena)
    ]),
]

Product = env['product.product']
SaleOrder = env['sale.order']
grand_total = 0.0
creados = []
fallidos = []

for partner_id, nombre_esperado, lineas in ORDERS:
    partner = env['res.partner'].browse(partner_id)
    if not partner.exists() or partner.name != nombre_esperado:
        print(f"!! SALTADO: partner {partner_id} no coincide (esperado {nombre_esperado!r}, "
              f"encontrado {partner.name!r}) — revisar antes de continuar.")
        fallidos.append((nombre_esperado, "partner no coincide"))
        continue

    order_lines = []
    for product_id, qty, precio_override, nota_extra in lineas:
        product = Product.browse(product_id)
        precio = precio_override if precio_override is not None else product.lst_price
        nombre_linea = product.name
        if nota_extra:
            nombre_linea = f"{nombre_linea} {nota_extra}"
        order_lines.append((0, 0, {
            'product_id': product.id,
            'name': nombre_linea,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'price_unit': precio,
        }))

    try:
        with env.cr.savepoint():
            so = SaleOrder.create({
                'partner_id': partner.id,
                'client_order_ref': REF,
                'note': NOTA,
                'custom_payment_method': 'efectivo',
                'custom_itbms_required': False,
                'order_line': order_lines,
            })
            so.with_context(skip_payment_method_check=True).action_confirm()
            grand_total += so.amount_total
            creados.append((so.name, partner.name, so.amount_total, so.state))
            print(f"Confirmada {so.name} | {partner.name} | total={so.amount_total:.2f} | "
                  f"estado={so.state} | id={so.id}")
    except Exception as e:
        print(f"!! ERROR creando/confirmando orden de {nombre_esperado}: {e}")
        fallidos.append((nombre_esperado, str(e)))

env.cr.commit()

print("\n========== RESUMEN ==========")
for name, partner_name, total, state in creados:
    print(f"  {name} | {partner_name} | ${total:.2f} | {state}")
if fallidos:
    print("\n-- Con problemas (no se crearon) --")
    for partner_name, motivo in fallidos:
        print(f"  {partner_name}: {motivo}")
print(f"\nTOTAL DE LAS {len(creados)} ÓRDENES CONFIRMADAS: ${grand_total:.2f}")
print(f"\nBuscar en Odoo con la Referencia del cliente = '{REF}' para verlas todas juntas.")
print("Recordatorio: al confirmarse se generaron los traslados de Inventario "
      "correspondientes (reservan stock real) — si son solo de prueba, cancelar "
      "después esas órdenes/traslados para liberar el stock.")
PYEOF
