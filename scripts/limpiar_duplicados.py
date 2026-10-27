# Se ejecuta DENTRO de `odoo shell` (lo lanza limpiar_duplicados.sh; `env` ya existe). No usar a mano.
# Borra los productos ARCHIVADOS que tienen un gemelo ACTIVO con el mismo código de barras y NINGÚN historial
# (sin movimientos, ventas, facturas, compras, existencias, etc.). Los que sí tienen historial NO se tocan.
# Aparte: unifica las copias archivadas de CREMA CORPORAL NNP HONEY & OATMEAL 590ML (código 841670029904).
# Sin APPLY=1 es SIMULACRO: no cambia nada.
import json
import os

APPLY = os.environ.get('APPLY') == '1'
P = env['product.product'].with_context(active_test=False)
HISTORY = [
    ('stock.move', 'product_id'), ('stock.move.line', 'product_id'), ('stock.quant', 'product_id'),
    ('sale.order.line', 'product_id'), ('account.move.line', 'product_id'),
    ('purchase.order.line', 'product_id'), ('product.supplierinfo', 'product_id'),
    ('stock.warehouse.orderpoint', 'product_id'), ('stock.lot', 'product_id'),
]


def history(products):
    """{product_id: cantidad de registros que lo usan}"""
    count = {p.id: 0 for p in products}
    for model, field in HISTORY:
        if model not in env.registry:
            continue
        for row in env[model].with_context(active_test=False).search_read([(field, 'in', products.ids)], [field]):
            count[row[field][0]] += 1
    return count


def backup(p):
    print('RESPALDO ' + json.dumps({
        'id': p.id, 'template_id': p.product_tmpl_id.id, 'name': p.name, 'barcode': p.barcode,
        'default_code': p.default_code, 'list_price': p.list_price, 'standard_price': p.standard_price,
        'categ': p.categ_id.display_name, 'create_date': str(p.create_date),
        'extra_barcodes': p.barcode_ids.mapped('name') if 'barcode_ids' in p._fields else [],
    }, ensure_ascii=False))


def delete(p):
    try:
        with env.cr.savepoint():
            p.unlink()
        return True
    except Exception as e:  # tiene algo que Odoo no deja borrar: se deja como está
        print('  NO SE PUDO BORRAR id=%s %s: %s' % (p.id, p.name, str(e).splitlines()[0][:120]))
        return False


print('== MODO: %s ==' % ('APLICAR' if APPLY else 'SIMULACRO (no cambia nada)'))

# 1) archivados con gemelo activo (mismo código de barras)
archived = P.search([('active', '=', False), ('barcode', '!=', False)])
twins = set(P.search([('active', '=', True), ('barcode', 'in', archived.mapped('barcode'))]).mapped('barcode'))
cand = archived.filtered(lambda p: p.barcode in twins)
hist = history(cand)
sin_historial = cand.filtered(lambda p: not hist[p.id])
con_historial = cand - sin_historial
print('Archivados con gemelo activo: %d | sin historial (se borran): %d | con historial (NO se tocan): %d'
      % (len(cand), len(sin_historial), len(con_historial)))
for p in con_historial:
    print('  CON HISTORIAL (se queda): id=%s %s [%s] registros=%s' % (p.id, p.name, p.barcode, hist[p.id]))

borrados = 0
for p in sin_historial:
    backup(p)
    if APPLY and delete(p):
        borrados += 1
print('Borrados: %d' % borrados)

# 2) CREMA CORPORAL NNP HONEY & OATMEAL 590ML: queda UNA (la de más historial); las demás sin historial se borran
copies = P.search([('barcode', '=', '841670029904')])
h2 = history(copies)
print('NNP HONEY & OATMEAL: copias=%s historial=%s' % (copies.ids, h2))
with_h = copies.filtered(lambda p: h2[p.id])
if len(with_h) > 1:
    print('  ATENCIÓN: más de una copia tiene historial; hay que fusionarlas a mano (no se tocó nada).')
else:
    keep = with_h or copies[:1]
    for p in copies - keep:
        backup(p)
        print('  queda id=%s; se borra id=%s' % (keep.id, p.id))
        if APPLY:
            delete(p)

if APPLY:
    env.cr.commit()
    print('LISTO: cambios guardados.')
else:
    env.cr.rollback()
    print('Simulacro terminado: no se cambió nada. Para aplicar, repetir con --apply.')
