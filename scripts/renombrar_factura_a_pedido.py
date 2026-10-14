#!/usr/bin/env python3
"""Cambia en Odoo la palabra "factura" por "pedido" en lo que ven las chicas (idioma es_419).

Solo cambia NOMBRES EN PANTALLA (menús, acciones, etiquetas de campos y valores de estado). No toca
ids internos, datos, impuestos ni documentos fiscales.

Uso (mismas variables de entorno ODOO_* que odoo_rpc.py):
    python3 scripts/renombrar_factura_a_pedido.py                  # simulacro: muestra antes -> después
    python3 scripts/renombrar_factura_a_pedido.py --apply          # aplica (solo tras el "sí" de Andrés)
    python3 scripts/renombrar_factura_a_pedido.py --apply --solo menus   # solo un grupo
Es repetible: si una actualización de Odoo devuelve algún nombre, se vuelve a correr.
Para revertir: python3 scripts/renombrar_factura_a_pedido.py --apply --revertir
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odoo_rpc import call  # noqa: E402

CTX = {'lang': 'es_419'}

# (modelo, id, campo, nombre ANTES, nombre DESPUÉS)
MENUS = [
    ('ir.ui.menu', 124, 'name', 'Facturación', 'Pedidos'),
    ('ir.ui.menu', 127, 'name', 'Facturas', 'Pedidos'),
    ('ir.ui.menu', 134, 'name', 'Facturas de proveedor', 'Pedidos de proveedor'),
    ('ir.ui.menu', 147, 'name', 'Análisis de facturas', 'Análisis de pedidos'),
    ('ir.ui.menu', 152, 'name', 'Facturación', 'Pedidos'),
    ('ir.ui.menu', 191, 'name', 'Por facturar', 'Por generar pedido'),
    ('ir.ui.menu', 192, 'name', 'Órdenes a facturar', 'Órdenes por generar pedido'),
]
ACCIONES = [
    ('ir.actions.act_window', 261, 'name', 'Facturas', 'Pedidos'),
    ('ir.actions.act_window', 262, 'name', 'Facturas', 'Pedidos'),
    ('ir.actions.act_window', 336, 'name', 'Facturas', 'Pedidos'),
    ('ir.actions.act_window', 293, 'name', 'Análisis de facturas', 'Análisis de pedidos'),
    ('ir.actions.act_window', 312, 'name', 'Análisis de facturas', 'Análisis de pedidos'),
    ('ir.actions.act_window', 327, 'name', 'Crear facturas', 'Generar pedidos'),
    ('ir.actions.act_window', 331, 'name', 'Órdenes a facturar', 'Órdenes por generar pedido'),
    ('ir.actions.act_window', 528, 'name', 'Órdenes a facturar', 'Órdenes por generar pedido'),
]
# Etiquetas de campos: se buscan por (modelo, nombre técnico) para no depender de ids.
CAMPOS = [
    ('sale.order', 'invoice_status', 'Estado de generación de pedido'),
    ('sale.order', 'invoice_count', 'Número de pedidos'),
    ('sale.order', 'invoice_ids', 'Pedidos'),
    ('sale.order', 'partner_invoice_id', 'Dirección del pedido'),
    ('sale.order', 'journal_id', 'Diario de pedidos'),
    ('sale.order', 'amount_invoiced', 'Pedido generado'),
    ('sale.order', 'amount_to_invoice', 'Balance sin generar pedido'),
    ('sale.order.line', 'invoice_status', 'Estado de generación de pedido'),
    ('sale.order.line', 'invoice_lines', 'Líneas del pedido generado'),
    ('sale.order.line', 'qty_invoiced', 'Cantidad en pedido'),
    ('sale.order.line', 'qty_invoiced_posted', 'Cantidad en pedido (registrada)'),
    ('sale.order.line', 'qty_to_invoice', 'Cantidad por generar pedido'),
    ('sale.order.line', 'amount_invoiced', 'Importe en pedido'),
    ('sale.order.line', 'amount_to_invoice', 'Balance sin generar pedido'),
    ('sale.order.line', 'untaxed_amount_invoiced', 'Importe sin impuestos en pedido'),
    ('sale.order.line', 'untaxed_amount_to_invoice', 'Importe sin impuestos por generar pedido'),
    ('res.partner', 'total_invoiced', 'Total en pedidos'),
]
# Valores del estado de facturación de la orden/línea (los que se ven como etiqueta en las listas).
ESTADOS = [
    ('no', 'Nada que facturar', 'Nada por generar pedido'),
    ('to invoice', 'Por facturar', 'Por generar pedido'),
    ('invoiced', 'Facturado por completo', 'Pedido generado por completo'),
]


def leer(modelo, ids, campo):
    filas = call(modelo, 'read', [ids], {'fields': [campo], 'context': CTX})
    return {f['id']: f[campo] for f in filas}


def escribir(modelo, rid, valores, aplicar):
    if aplicar:
        call(modelo, 'write', [[rid], valores], {'context': CTX}, allow_write=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='aplicar de verdad (por defecto es simulacro)')
    ap.add_argument('--revertir', action='store_true', help='volver a los nombres originales')
    ap.add_argument('--solo', choices=['menus', 'acciones', 'campos', 'estados'])
    opts = ap.parse_args()
    modo = 'REVERTIR' if opts.revertir else 'APLICAR'
    print(('== %s ==' % modo) if opts.apply else '== SIMULACRO (no se cambia nada; agrega --apply) ==')

    def grupo(nombre):
        return opts.solo in (None, nombre)

    for titulo, nombre, lista in (('MENÚS', 'menus', MENUS), ('ACCIONES', 'acciones', ACCIONES)):
        if not grupo(nombre):
            continue
        print('\n--- %s ---' % titulo)
        for modelo, rid, campo, antes, despues in lista:
            actual = leer(modelo, [rid], campo).get(rid)
            destino, esperado = (antes, despues) if opts.revertir else (despues, antes)
            marca = '' if actual in (esperado, destino) else '   ¡OJO: hoy dice "%s"!' % actual
            print('%s %s: "%s" -> "%s"%s' % (modelo, rid, actual, destino, marca))
            if actual == destino:
                continue
            if marca:
                continue
            escribir(modelo, rid, {campo: destino}, opts.apply)

    if grupo('campos'):
        print('\n--- ETIQUETAS DE CAMPOS ---')
        for modelo, nombre, nuevo in CAMPOS:
            filas = call('ir.model.fields', 'search_read', [[('model', '=', modelo), ('name', '=', nombre)]],
                         {'fields': ['id'], 'limit': 1})
            ids = [f['id'] for f in filas]
            if not ids:
                print('%s.%s: no existe, se omite' % (modelo, nombre))
                continue
            actual = leer('ir.model.fields', ids, 'field_description')[ids[0]]
            if opts.revertir:
                print('%s.%s: revertir a mano si hace falta (hoy "%s")' % (modelo, nombre, actual))
                continue
            print('%s.%s: "%s" -> "%s"' % (modelo, nombre, actual, nuevo))
            if actual != nuevo:
                escribir('ir.model.fields', ids[0], {'field_description': nuevo}, opts.apply)

    if grupo('estados'):
        print('\n--- VALORES DEL ESTADO (etiquetas en las listas) ---')
        for valor, antes, despues in ESTADOS:
            filas = call('ir.model.fields.selection', 'search_read',
                         [[('field_id.name', '=', 'invoice_status'),
                           ('field_id.model', 'in', ['sale.order', 'sale.order.line']), ('value', '=', valor)]],
                         {'fields': ['id']})
            ids = [f['id'] for f in filas]
            for rid in ids:
                actual = leer('ir.model.fields.selection', [rid], 'name')[rid]
                destino = antes if opts.revertir else despues
                print('selection %s (%s): "%s" -> "%s"' % (rid, valor, actual, destino))
                if actual != destino:
                    escribir('ir.model.fields.selection', rid, {'name': destino}, opts.apply)

    if not opts.apply:
        print('\nSimulacro terminado. Nada se cambió.')


if __name__ == '__main__':
    main()
