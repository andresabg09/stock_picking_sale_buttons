/* Versión H — encabezado: menú del celular/tablet y ventana del escáner.
 * JS plano (sin módulos de Odoo), igual que header_search.js. No hace nada si la página no
 * trae el encabezado H (clase `dkh` ausente). */
(function () {
    'use strict';

    var lastFocus = null;

    function byId(id) {
        return document.getElementById(id);
    }

    function openScan() {
        var box = byId('dkh-scan');
        if (!box) {
            return;
        }
        lastFocus = document.activeElement;
        box.hidden = false;
        document.body.classList.add('dkh-lock');
        var input = byId('dkh-code');
        if (input) {
            input.focus();
        }
    }

    function closeScan() {
        var box = byId('dkh-scan');
        if (!box || box.hidden) {
            return;
        }
        box.hidden = true;
        document.body.classList.remove('dkh-lock');
        if (lastFocus && lastFocus.focus) {
            lastFocus.focus();
        }
    }

    function toggleDrawer() {
        var drawer = byId('dkh-drawer');
        var btn = document.querySelector('[data-dkh-burger]');
        if (!drawer) {
            return;
        }
        drawer.hidden = !drawer.hidden;
        if (btn) {
            btn.setAttribute('aria-expanded', drawer.hidden ? 'false' : 'true');
        }
    }

    document.addEventListener('click', function (ev) {
        var t = ev.target.closest ? ev.target.closest('[data-dkh-scan], [data-dkh-burger], .dkh-scrim') : null;
        if (!t) {
            return;
        }
        if (t.matches('[data-dkh-scan="open"]')) {
            ev.preventDefault();
            openScan();
        } else if (t.matches('[data-dkh-scan="close"]')) {
            ev.preventDefault();
            closeScan();
        } else if (t.matches('[data-dkh-burger]')) {
            ev.preventDefault();
            toggleDrawer();
        } else if (t.classList.contains('dkh-scrim') && ev.target === t) {
            closeScan(); // clic en el fondo oscuro
        }
    });

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') {
            closeScan();
        }
    });
})();
