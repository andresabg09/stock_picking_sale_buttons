#!/usr/bin/env python3
"""Lectura y escritura (con seguro) al Odoo de producción por JSON-RPC (reemplazo gratuito del conector MCP).

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

Escrituras (cambian la BD de producción; CLAUDE.md regla 6: antes se le explica a Andrés qué se va a hacer y
se espera su "sí" explícito, caso por caso). Por defecto son SIMULACRO: solo muestran qué harían. Solo se
ejecutan de verdad con --apply, que se agrega únicamente DESPUÉS de la confirmación de Andrés:
    python3 scripts/odoo_rpc.py write stock.picking 123 '{"note":"x"}'                 # simulacro
    python3 scripts/odoo_rpc.py write stock.picking 123 '{"note":"x"}' --apply         # ejecuta
    python3 scripts/odoo_rpc.py create res.partner '{"name":"Prueba"}' --apply
    python3 scripts/odoo_rpc.py call stock.picking 123 action_cancel --apply            # método de negocio
    python3 scripts/odoo_rpc.py write product.public.category 330 '{"name":"Tratamientos"}' \
        --context '{"lang":"es_419"}' --apply                                          # campos traducibles
NO hay "borrar" (unlink): para quitar algo se archiva (write active=False) o se cancela con su método.
"""
import argparse
import json
import os
import sys
import urllib.request

READ_METHODS = {'search_read', 'search_count', 'read', 'fields_get', 'name_search'}
FORBIDDEN_METHODS = {'unlink'}


def _env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        sys.exit(f'Falta la variable de entorno {name}. Se configura en el entorno de Claude Code '
                 '(Edit -> variables de entorno / secretos); nunca se pega en el chat.')
    return value


def call(model, method, args, kwargs=None, allow_write=False):
    if method in FORBIDDEN_METHODS or method.startswith('_'):
        sys.exit(f'Método "{method}" no permitido (ni borrar ni métodos privados).')
    if method not in READ_METHODS and not allow_write:
        sys.exit(f'Método "{method}" no es de lectura: se ejecuta solo con --apply, tras la confirmación de Andrés.')
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
    parser.add_argument('action', help='search_read | search_count | read | fields_get | name_search | module '
                                       '| write | create | call')
    parser.add_argument('model', help='modelo (ej. sale.order) o, con "module", el nombre técnico del módulo')
    parser.add_argument('arg', nargs='?', default='[]',
                        help='dominio JSON (search_*), ids (read) o texto (name_search)')
    parser.add_argument('fields', nargs='?', default='', help='campos separados por coma')
    parser.add_argument('--limit', type=int, default=80)
    parser.add_argument('--order', default=None)
    parser.add_argument('--attrs', default='string,type')
    parser.add_argument('--apply', action='store_true',
                        help='ejecuta de verdad la escritura (sin esto es simulacro). Solo tras el "sí" de Andrés')
    parser.add_argument('--context', default='{}', help='contexto JSON (ej. {"lang":"es_419"})')
    opts = parser.parse_args()

    fields = [f for f in opts.fields.split(',') if f]
    if opts.action == 'module':
        result = call('ir.module.module', 'search_read', [[['name', '=', opts.model]]],
                      {'fields': ['name', 'state', 'latest_version', 'installed_version', 'write_date']})
    elif opts.action == 'search_read':
        kwargs = {'fields': fields, 'limit': opts.limit}
        _ctx = json.loads(opts.context)
        if _ctx:
            kwargs['context'] = _ctx
        if opts.order:
            kwargs['order'] = opts.order
        result = call(opts.model, 'search_read', [json.loads(opts.arg)], kwargs)
    elif opts.action == 'search_count':
        result = call(opts.model, 'search_count', [json.loads(opts.arg)])
    elif opts.action == 'read':
        ids = json.loads(opts.arg)
        _ctx = json.loads(opts.context)
        result = call(opts.model, 'read', [ids if isinstance(ids, list) else [ids]], dict({'fields': fields}, **({'context': _ctx} if _ctx else {})))
    elif opts.action == 'fields_get':
        result = call(opts.model, 'fields_get', [], {'attributes': opts.attrs.split(',')})
    elif opts.action == 'name_search':
        result = call(opts.model, 'name_search', [opts.arg], {'limit': opts.limit})
    elif opts.action in ('write', 'create', 'call'):
        context = json.loads(opts.context)
        if opts.action == 'write':
            ids = json.loads(opts.arg)
            args = [ids if isinstance(ids, list) else [ids], json.loads(opts.fields)]
            method = 'write'
        elif opts.action == 'create':
            args = [json.loads(opts.arg)]
            method = 'create'
        else:
            ids = json.loads(opts.arg)
            args = [ids if isinstance(ids, list) else [ids]]
            method = opts.fields
            if not method:
                sys.exit('Falta el nombre del método (ej. action_cancel).')
        kwargs = {'context': context} if context else {}
        if not opts.apply:
            print('SIMULACRO (no se cambió nada). Para ejecutar, tras la confirmación de Andrés, agrega --apply:')
            print(json.dumps({'modelo': opts.model, 'método': method, 'args': args, 'kwargs': kwargs},
                             ensure_ascii=False, indent=1))
            return
        result = call(opts.model, method, args, kwargs, allow_write=True)
    else:
        sys.exit(f'Acción desconocida: {opts.action}')
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
