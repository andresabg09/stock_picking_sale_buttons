/* Acceso a la tienda: cerrar la franja "No has iniciado sesión" (vuelve en la próxima visita) y cerrar el menú de la
   cuenta al tocar fuera. JS plano, igual que dkh_shell.js. */
(function () {
    'use strict';

    var KEY = 'dkh_strip_off';

    function stripOff() {
        try { return window.sessionStorage.getItem(KEY) === '1'; } catch (e) { return false; }
    }

    function init() {
        var strip = document.getElementById('dkh-strip');
        if (strip && stripOff() && !strip.classList.contains('is-cart')) {
            strip.hidden = true;
        }
    }

    document.addEventListener('click', function (ev) {
        var close = ev.target.closest && ev.target.closest('[data-dkh-strip="close"]');
        if (close) {
            var strip = document.getElementById('dkh-strip');
            if (strip) { strip.hidden = true; }
            try { window.sessionStorage.setItem(KEY, '1'); } catch (e) { /* sin almacenamiento: solo se cierra ahora */ }
            return;
        }
        var open = document.querySelector('details.dkh-me[open]');
        if (open && !open.contains(ev.target)) {
            open.removeAttribute('open');
        }
    });

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') {
            var open = document.querySelector('details.dkh-me[open]');
            if (open) { open.removeAttribute('open'); }
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
