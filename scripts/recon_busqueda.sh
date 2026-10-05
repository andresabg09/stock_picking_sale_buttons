#!/bin/bash
# Solo LECTURA: imprime el código real de Odoo que maneja la búsqueda de la tienda
# (website / website_sale) y las extensiones de PostgreSQL. No modifica nada.
# Uso: sudo bash scripts/recon_busqueda.sh
set -u
CID=$(docker ps --filter "name=crm_odoo." --format "{{.Names}}" | head -n1)
DB_HOST=$(docker exec "$CID" printenv HOST)
DB_PORT=$(docker exec "$CID" printenv PORT)
DB_USER=$(docker exec "$CID" printenv USER)
DB_PASS=$(docker exec "$CID" printenv PASSWORD)

docker exec -i "$CID" odoo shell -d shalom --no-http \
  --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASS" 2>/dev/null <<'PYEOF'
import inspect

def show_methods(model_name, names):
    cls = type(env[model_name])
    for name in names:
        found = False
        for c in cls.__mro__:
            f = c.__dict__.get(name)
            if f is None:
                continue
            f = getattr(f, '__func__', f)
            try:
                src = inspect.getsource(f)
            except Exception as e:
                src = '(sin fuente: %s)' % e
            print('\n===== %s.%s  [%s] =====' % (model_name, name, c.__module__))
            print(src)
            found = True
        if not found:
            print('\n===== %s.%s  NO EXISTE =====' % (model_name, name))

show_methods('website', ['_search_with_fuzzy', '_search_exact', '_search_get_details', '_search_render_results'])
show_methods('website.searchable.mixin', ['_search_build_domain', '_search_get_detail', '_search_fetch', '_search_render_results'])
show_methods('product.template', ['_search_get_detail', '_search_fetch', '_search_render_results'])

import importlib
for modname, clsname, meths in [
    ('odoo.addons.website_sale.controllers.main', 'WebsiteSale', ['_shop_lookup_products', '_get_search_options', '_get_search_domain']),
    ('odoo.addons.website.controllers.main', 'Website', ['autocomplete']),
]:
    try:
        cls = getattr(importlib.import_module(modname), clsname)
    except Exception as e:
        print('\n===== %s.%s no importable: %s' % (modname, clsname, e))
        continue
    for m in meths:
        f = getattr(cls, m, None)
        if f is None:
            print('\n===== %s.%s NO EXISTE' % (clsname, m))
            continue
        f = getattr(f, '__wrapped__', f)
        try:
            print('\n===== %s.%s =====' % (clsname, m))
            print(inspect.getsource(f))
        except Exception as e:
            print('(sin fuente: %s)' % e)

for key in ['website_sale.search', 'website.s_searchbar_input', 'website.header_search_box']:
    v = env['ir.ui.view'].search([('key', '=', key)], limit=1)
    print('\n===== VISTA %s =====' % key)
    print(v.arch_db if v else 'NO EXISTE')

env.cr.execute("select extname from pg_extension order by 1")
print('\n===== EXTENSIONES PG =====')
print([r[0] for r in env.cr.fetchall()])
PYEOF
