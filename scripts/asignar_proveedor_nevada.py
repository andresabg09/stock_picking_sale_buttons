#!/usr/bin/env python3
"""Deja a NEVADA ZONA UNO como proveedor de los productos (activos y archivados) que hoy tienen líneas de
proveedor de Greenpeak (el Nevada viejo, archivado) o de DISTRIBUIDORA DIANKE.

Reglas (pedidas por Andrés, 2026-10-21):
  - Solo se tocan productos que YA tienen alguna línea de Greenpeak o de Distribuidora Dianke; los productos sin
    ninguna línea de proveedor NO se tocan.
  - Si el producto ya tiene línea de Nevada Zona Uno, se actualiza; si no, la línea de Greenpeak se CONVIERTE en
    Nevada Zona Uno (equivale a borrar la de Greenpeak y crear la de Nevada); si solo tenía Distribuidora Dianke,
    se crea la línea de Nevada.
  - Precio de la línea de Nevada = el MÁS BAJO entre el costo del producto en Dianke y los precios de sus líneas de
    proveedor (solo valores mayores que 0).
  - Las líneas de Distribuidora Dianke no se borran: se les baja la prioridad (sequence 10). Nevada queda en 1.

Uso (desde la raíz del repo; usa las mismas variables de entorno que odoo_rpc.py):
    python3 scripts/asignar_proveedor_nevada.py                 # simulacro: solo cuenta y muestra ejemplos
    python3 scripts/asignar_proveedor_nevada.py --apply         # aplica (solo tras el "sí" de Andrés, regla 6)
El respaldo del estado anterior (ids, proveedor, precio, prioridad) se escribe en --backup (FUERA del repo: el repo
es público y trae los costos). Con él se puede revertir.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import odoo_rpc as rpc  # noqa: E402

DIANKE_COMPANY = 1
NEVADA_ZONA_UNO = 2269        # res.partner "NEVADA ZONA UNO" (el proveedor vigente)
GREENPEAK = 8                 # res.partner viejo (archivado) con 1.064 líneas
DISTRIBUIDORA_DIANKE = 2331
LOW_PRIORITY = 10
CTX = {'active_test': False, 'allowed_company_ids': [DIANKE_COMPANY]}
BATCH = 200


def search_read(model, domain, fields):
    return rpc.call(model, 'search_read', [domain], {'fields': fields, 'context': CTX})


def build_plan():
    lines = search_read('product.supplierinfo', [], ['partner_id', 'product_tmpl_id', 'price', 'sequence'])
    by_tmpl = collections.defaultdict(list)
    for line in lines:
        by_tmpl[line['product_tmpl_id'][0]].append(line)
    affected = [tid for tid, ls in by_tmpl.items()
                if any(l['partner_id'][0] in (GREENPEAK, DISTRIBUIDORA_DIANKE) for l in ls)]
    templates = {t['id']: t for t in search_read(
        'product.template', [['id', 'in', affected]], ['name', 'active', 'standard_price', 'type'])}
    plan = {'convert': [], 'update': [], 'create': [], 'demote': [], 'skipped_no_price': []}
    for tid in affected:
        tmpl, ls = templates[tid], by_tmpl[tid]
        prices = [l['price'] for l in ls if l['price'] > 0]
        if tmpl['standard_price'] > 0:
            prices.append(tmpl['standard_price'])
        if not prices:
            plan['skipped_no_price'].append(tmpl['name'])
            continue
        price = round(min(prices), 4)
        nevada = [l for l in ls if l['partner_id'][0] == NEVADA_ZONA_UNO]
        greenpeak = [l for l in ls if l['partner_id'][0] == GREENPEAK]
        distribuidora = [l for l in ls if l['partner_id'][0] == DISTRIBUIDORA_DIANKE]
        if nevada:
            plan['update'].append({'line': nevada[0], 'tmpl': tmpl, 'price': price})
        elif greenpeak:
            plan['convert'].append({'line': greenpeak[0], 'tmpl': tmpl, 'price': price})
        else:
            plan['create'].append({'tmpl': tmpl, 'price': price})
        plan['demote'] += [l for l in distribuidora if l['sequence'] != LOW_PRIORITY]
        # líneas de Greenpeak sobrantes (más de una por producto): se pasan a prioridad baja, no se borran
    return plan, by_tmpl


def summarize(plan):
    changed = [p for p in plan['convert'] if abs(p['line']['price'] - p['price']) > 0.005]
    print('Productos tocados: %d (activos %d, archivados %d)' % (
        len(plan['convert']) + len(plan['update']) + len(plan['create']),
        sum(1 for k in ('convert', 'update', 'create') for p in plan[k] if p['tmpl']['active']),
        sum(1 for k in ('convert', 'update', 'create') for p in plan[k] if not p['tmpl']['active'])))
    print('  línea de Greenpeak -> NEVADA ZONA UNO: %d (de ellos %d cambian de precio)' % (len(plan['convert']), len(changed)))
    print('  ya tenían Nevada Zona Uno (se actualiza el precio): %d (%d cambian de precio)' % (
        len(plan['update']), sum(1 for p in plan['update'] if abs(p['line']['price'] - p['price']) > 0.005)))
    print('  solo tenían Distribuidora Dianke -> se crea la línea de Nevada: %d' % len(plan['create']))
    print('  líneas de Distribuidora Dianke con prioridad baja: %d' % len(plan['demote']))
    print('  sin ningún precio > 0 (no se tocan): %d' % len(plan['skipped_no_price']))
    for p in sorted(changed, key=lambda p: -abs(p['line']['price'] - p['price']))[:8]:
        print('    ej.: %s (%s): %s -> %s' % (p['tmpl']['name'], 'activo' if p['tmpl']['active'] else 'archivado',
                                              p['line']['price'], p['price']))


def apply(plan, backup_path):
    backup = {'convert': [{'id': p['line']['id'], 'partner_id': p['line']['partner_id'][0],
                           'price': p['line']['price'], 'sequence': p['line']['sequence']} for p in plan['convert']],
              'update': [{'id': p['line']['id'], 'price': p['line']['price']} for p in plan['update']],
              'demote': [{'id': l['id'], 'sequence': l['sequence']} for l in plan['demote']],
              'created': []}
    with open(backup_path, 'w') as handle:
        json.dump(backup, handle)
    print('Respaldo previo escrito en', backup_path)

    def write(ids, vals):
        rpc.call('product.supplierinfo', 'write', [ids, vals], {'context': CTX}, allow_write=True)

    by_price = collections.defaultdict(list)
    for p in plan['convert']:
        by_price[p['price']].append(p['line']['id'])
    for price, ids in by_price.items():
        for i in range(0, len(ids), BATCH):
            write(ids[i:i + BATCH], {'partner_id': NEVADA_ZONA_UNO, 'price': price, 'sequence': 1})
    by_price = collections.defaultdict(list)
    for p in plan['update']:
        by_price[p['price']].append(p['line']['id'])
    for price, ids in by_price.items():
        write(ids, {'price': price, 'sequence': 1})
    created = []
    new = plan['create']
    for i in range(0, len(new), BATCH):
        vals = [{'product_tmpl_id': p['tmpl']['id'], 'partner_id': NEVADA_ZONA_UNO, 'price': p['price'],
                 'min_qty': 1.0, 'sequence': 1, 'company_id': DIANKE_COMPANY} for p in new[i:i + BATCH]]
        created += rpc.call('product.supplierinfo', 'create', [vals], {'context': CTX}, allow_write=True)
    backup['created'] = created
    ids = [l['id'] for l in plan['demote']]
    for i in range(0, len(ids), BATCH):
        write(ids[i:i + BATCH], {'sequence': LOW_PRIORITY})
    with open(backup_path, 'w') as handle:
        json.dump(backup, handle)
    print('Aplicado. Líneas creadas: %d' % len(created))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='escribe en Odoo (solo tras el sí de Andrés)')
    parser.add_argument('--backup', default='/tmp/respaldo_proveedor_nevada.json')
    opts = parser.parse_args()
    plan, _ = build_plan()
    summarize(plan)
    if opts.apply:
        apply(plan, opts.backup)
    else:
        print('\nSIMULACRO: no se cambió nada. Agrega --apply para aplicar.')


if __name__ == '__main__':
    main()
