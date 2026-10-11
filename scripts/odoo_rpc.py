#!/usr/bin/env python3
"""Consulta de SOLO LECTURA al Odoo de producción por JSON-RPC (reemplazo gratuito del conector MCP).

Las credenciales NUNCA van en el repo ni en el chat: se leen de variables de entorno del entorno de
Claude Code (menú del entorno en la barra del título -> Edit -> variables de entorno / secretos):

    ODOO_URL      https://shalom-odoo.cjauws.easypanel.host   (solo esquema y host)
    ODOO_DB       shalom
    ODOO_UID      número del usuario dueño de la clave (ej. 2)
    ODOO_API_KEY  clave API del usuario (Odoo -> Preferencias -> Seguridad de la cuenta)

Uso (siempre pasar los campos):
    python3 scripts/odoo_rpc.py search_read sale.order '[["state","=","sale"]]' name,amount_total --limit 5
    python3 scripts/odoo_rpc.py search_count stock.picking '[["state","=","assigned"]]'
    python3 scripts/odoo_rpc.py read product.product 3431 name,free_qty,qty_available
    python3 scripts/odoo_rpc.py fields_get product.template --attrs string,type
    python3 scripts/odoo_rpc.py module stock_picking_sale_buttons     # estado y versión de un módulo

Solo permite métodos de lectura. Las escrituras (crear/modificar/borrar) NO están aquí: cambian la BD de
producción y requieren la confirmación explícita de Andrés, caso por caso (ver CLAUDE.md, regla 6).
"""
import argparse
import json
import os
import sys
import urllib.request

READ_METHODS = {'search_read', 'search_count', 'read', 'fields_get', 'name_search'}


def _env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        sys.exit(f'Falta la variable de entorno {name}. Se configura en el entorno de Claude Code '
                 '(Edit -> variables de entorno / secretos); nunca se pega en el chat.')
    return value


def call(model, method, args, kwargs=None):
    if method not in READ_METHODS:
        sys.exit(f'Método "{method}" no permitido: este script es solo de lectura.')
    url = _env('ODOO_URL').rstrip('/') + '/jsonrpc'
    payload = {
        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
        'params': {
            'service': 'object', 'method': 'execute_kw',
            'args': [_env('ODOO_DB'), int(_env('ODOO_UID')), _env('ODOO_API_KEY'),
                     model, method, args, kwargs or {}],
        },
    }
    request = urllib.request.Request(url, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    if data.get('error'):
        error = data['error'].get('data', {}).get('message') or data['error'].get('message')
        sys.exit(f'Odoo respondió con error: {error}')
    return data.get('result')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', help='search_read | search_count | read | fields_get | name_search | module')
    parser.add_argument('model', help='modelo (ej. sale.order) o, con "module", el nombre técnico del módulo')
    parser.add_argument('arg', nargs='?', default='[]',
                        help='dominio JSON (search_*), ids (read) o texto (name_search)')
    parser.add_argument('fields', nargs='?', default='', help='campos separados por coma')
    parser.add_argument('--limit', type=int, default=80)
    parser.add_argument('--order', default=None)
    parser.add_argument('--attrs', default='string,type')
    opts = parser.parse_args()

    fields = [f for f in opts.fields.split(',') if f]
    if opts.action == 'module':
        result = call('ir.module.module', 'search_read', [[['name', '=', opts.model]]],
                      {'fields': ['name', 'state', 'latest_version', 'installed_version', 'write_date']})
    elif opts.action == 'search_read':
        kwargs = {'fields': fields, 'limit': opts.limit}
        if opts.order:
            kwargs['order'] = opts.order
        result = call(opts.model, 'search_read', [json.loads(opts.arg)], kwargs)
    elif opts.action == 'search_count':
        result = call(opts.model, 'search_count', [json.loads(opts.arg)])
    elif opts.action == 'read':
        ids = json.loads(opts.arg)
        result = call(opts.model, 'read', [ids if isinstance(ids, list) else [ids]], {'fields': fields})
    elif opts.action == 'fields_get':
        result = call(opts.model, 'fields_get', [], {'attributes': opts.attrs.split(',')})
    elif opts.action == 'name_search':
        result = call(opts.model, 'name_search', [opts.arg], {'limit': opts.limit})
    else:
        sys.exit(f'Acción desconocida: {opts.action}')
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
