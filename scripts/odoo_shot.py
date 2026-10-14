#!/usr/bin/env python3
"""Capturas de pantalla de Odoo para que Claude revise el DISEÑO (cortes, botones, colores) sin que Andrés
tenga que mandar fotos. SOLO MIRA: abre una página y toma la captura; no guarda ni cambia nada.

Credenciales: variables de entorno del entorno de Claude Code (nunca en el chat ni en el repo):
    ODOO_URL            ya existe (la misma de odoo_rpc.py)
    ODOO_DB             ya existe
    ODOO_WEB_LOGIN      correo/usuario de un usuario de Odoo con contraseña (idealmente uno de SOLO LECTURA)
    ODOO_WEB_PASSWORD   contraseña de ese usuario
(La clave de API ODOO_API_KEY NO sirve para entrar al navegador: Odoo la acepta solo para datos.)

Uso:
    python3 scripts/odoo_shot.py /odoo/customer-invoices/1211 --out pedido.png
    python3 scripts/odoo_shot.py /odoo/customer-invoices/1211 --mobile --out pedido_celular.png
    python3 scripts/odoo_shot.py /odoo/customer-invoices/1211 --click ".o_cp_action_menus button" --out menu.png
    python3 scripts/odoo_shot.py /inicio --public --out inicio.png          # tienda pública, sin iniciar sesión
Opciones: --mobile (390x844) | --width/--height | --full (página completa) | --wait milisegundos |
          --click "selector css" (repetible; solo para abrir menús: se niega a pulsar botones que cambian datos).
"""
import argparse
import os
import sys

DANGEROUS = ('confirmar', 'publicar', 'eliminar', 'borrar', 'pagar', 'enviar', 'pasar a', 'marcar', 'volver',
             'guardar', 'crear', 'restablecer', 'cancelar', 'anular', 'descartar', 'armar', 'validar',
             'registrar', 'aplicar', 'quitar', 'nota de crédito')


def env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        sys.exit('Falta la variable de entorno %s (ver el encabezado de este script).' % name)
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path', help='ruta dentro de Odoo, ej. /odoo/customer-invoices/1211')
    ap.add_argument('--out', default='odoo_shot.png')
    ap.add_argument('--mobile', action='store_true')
    ap.add_argument('--width', type=int, default=0)
    ap.add_argument('--height', type=int, default=0)
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--public', action='store_true', help='sin iniciar sesión')
    ap.add_argument('--wait', type=int, default=4000)
    ap.add_argument('--click', action='append', default=[], help='selector CSS a pulsar (solo menús)')
    opts = ap.parse_args()

    from playwright.sync_api import sync_playwright

    base = env('ODOO_URL').rstrip('/')
    width, height = (390, 844) if opts.mobile else (1440, 900)
    width = opts.width or width
    height = opts.height or height

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/opt/pw-browsers')
                                     + '/chromium-1194/chrome-linux/chrome')
        ctx = browser.new_context(viewport={'width': width, 'height': height}, locale='es-PA',
                                  is_mobile=opts.mobile, has_touch=opts.mobile, device_scale_factor=1)
        page = ctx.new_page()
        if not opts.public:
            login, password, db = env('ODOO_WEB_LOGIN'), env('ODOO_WEB_PASSWORD'), env('ODOO_DB')
            page.goto('%s/web/login?db=%s' % (base, db), wait_until='domcontentloaded')
            page.fill('input[name=login]', login)
            page.fill('input[name=password]', password)
            page.click('button[type=submit]')
            page.wait_for_url('**/odoo**', timeout=60000)
        page.goto(base + opts.path, wait_until='domcontentloaded')
        page.wait_for_timeout(opts.wait)
        for selector in opts.click:
            target = page.locator(selector).first
            label = (target.inner_text() or '').strip().lower()
            if any(word in label for word in DANGEROUS):
                sys.exit('Me niego a pulsar "%s": parece una acción que cambia datos.' % label)
            target.click()
            page.wait_for_timeout(1200)
        page.screenshot(path=opts.out, full_page=opts.full)
        browser.close()
    print('Captura guardada en %s' % opts.out)


if __name__ == '__main__':
    main()
