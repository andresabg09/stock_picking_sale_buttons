#!/bin/bash
# Solo LECTURA (no modifica nada). Segunda ronda de datos para la Fase 3:
# endpoint de agregar al carrito, formulario del buscador (autocompletado),
# buscador de términos parecidos y extensiones de PostgreSQL.
# Uso: sudo bash scripts/recon_busqueda2.sh
set -u
CID=$(docker ps --filter "name=crm_odoo." --format "{{.Names}}" | head -n1)
DB_HOST=$(docker exec "$CID" printenv HOST)
DB_PORT=$(docker exec "$CID" printenv PORT)
DB_USER=$(docker exec "$CID" printenv USER)
DB_PASS=$(docker exec "$CID" printenv PASSWORD)

docker exec -i "$CID" odoo shell -d shalom --no-http \
  --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASS" 2>/dev/null <<'PYEOF'
import inspect, importlib

def first_lines(f, n=40):
    f = getattr(f, '__func__', f)
    f = getattr(f, '__wrapped__', f)
    try:
        lines = [l for l in inspect.getsource(f).splitlines() if l.strip()]
    except Exception as e:
        return '(sin fuente: %s)' % e
    return '\n'.join(lines[:n])

cls = importlib.import_module('odoo.addons.website_sale.controllers.main').WebsiteSale
for m in ['cart_update', 'cart_update_json']:
    print('\n===== WebsiteSale.%s =====' % m)
    f = getattr(cls, m, None)
    print(first_lines(f, 30) if f else 'NO EXISTE')

for model, names in [('website', ['sale_get_order', '_search_find_fuzzy_term']),
                     ('sale.order', ['_cart_update'])]:
    mcls = type(env[model])
    for name in names:
        for c in mcls.__mro__:
            f = c.__dict__.get(name)
            if f is not None:
                print('\n===== %s.%s [%s] =====' % (model, name, c.__module__))
                print(first_lines(f, 28 if name != '_search_find_fuzzy_term' else 45))
                break
        else:
            print('\n===== %s.%s NO EXISTE =====' % (model, name))

for key in ['website.website_search_box_input', 'website.s_searchbar_input', 'website.header_search_box']:
    v = env['ir.ui.view'].search([('key', '=', key)], limit=1)
    print('\n===== VISTA %s =====' % key)
    print(v.arch_db if v else 'NO EXISTE')

for xmlid in ['sale.menu_sale_config', 'website_sale.menu_catalog', 'website_sale.menu_ecommerce_settings']:
    r = env.ref(xmlid, raise_if_not_found=False)
    print('\n===== XMLID %s =====' % xmlid, r.complete_name if r else 'NO EXISTE')

env.cr.execute("select extname from pg_extension order by 1")
print('\n===== EXTENSIONES PG =====')
print([r[0] for r in env.cr.fetchall()])
print('\n===== FIN =====')
PYEOF
