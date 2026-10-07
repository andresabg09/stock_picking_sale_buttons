/* Versión H — carrito en vivo: al subir, bajar, escribir o quitar una cantidad en el carrito,
 * el monto, las líneas y la barra del pedido mínimo se actualizan solos (sin refrescar).
 * Solo actúa en la vista previa / encendido (clase `dkh` en el body) y en líneas `.dk-cline`.
 * Toma el control en la fase de captura para que el JS nativo del carrito no intervenga. */
(function () {
    'use strict';

    var busy = false;
    var WAIT_MS = 900; // espera a que termine de sumar/restar antes de actualizar el carrito
    var timers = {};
    var SWAP = ['.dk-cart-head', '#cart_products', '.dkh-confirm', '#o_cart_summary', '#o_wsale_total_accordion'];

    function inDkh() {
        return document.body && document.body.classList.contains('dkh');
    }

    function lineOf(node) {
        return node && node.closest ? node.closest('.dk-cline') : null;
    }

    function rpc(url, params) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params })
        }).then(function (r) { return r.json(); });
    }

    // Trae el carrito actualizado y cambia solo las piezas que dependen de las cantidades.
    function refresh() {
        return fetch(window.location.href, { credentials: 'same-origin' })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, 'text/html');
                if (!doc.querySelector('#cart_products')) {
                    window.location.reload();
                    return;
                }
                SWAP.forEach(function (sel) {
                    var cur = document.querySelector(sel);
                    var neu = doc.querySelector(sel);
                    if (cur && neu) {
                        cur.replaceWith(neu);
                    }
                });
                var tot = document.querySelector('.dkh-cart-total');
                var ntot = doc.querySelector('.dkh-cart-total');
                if (tot && ntot) {
                    tot.textContent = ntot.textContent;
                }
            });
    }

    function setQty(line, qty) {
        var pid = parseInt(line.getAttribute('data-product-id'), 10);
        if (!pid) {
            return;
        }
        if (busy) {
            setTimeout(function () { setQty(line, qty); }, 250);
            return;
        }
        busy = true;
        line.classList.add('dk-busy');
        rpc('/shop/dk/set_qty', { product_id: pid, qty: qty }).then(function (d) {
            if (!d || d.error || (d.result && d.result.error)) {
                window.location.reload();
                return;
            }
            return refresh();
        }).catch(function () {
            window.location.reload();
        }).then(function () {
            busy = false;
            line.classList.remove('dk-busy');
        });
    }

    // Muestra la cantidad al instante y manda UNA sola actualización cuando deja de tocar.
    function schedule(line, qty) {
        var pid = line.getAttribute('data-product-id');
        var input = line.querySelector('input.js_quantity');
        if (input) {
            input.value = String(qty);
        }
        line.classList.add('dk-pending');
        clearTimeout(timers[pid]);
        timers[pid] = setTimeout(function () {
            var fresh = document.querySelector('.dk-cline[data-product-id="' + pid + '"]') || line;
            setQty(fresh, qty);
        }, WAIT_MS);
    }

    function current(line) {
        var input = line.querySelector('input.js_quantity');
        var n = input ? parseInt(input.value, 10) : 0;
        return n > 0 ? n : 0;
    }

    document.addEventListener('click', function (ev) {
        if (!inDkh()) {
            return;
        }
        var t = ev.target.closest ? ev.target.closest('.js_add_cart_json, .js_delete_product') : null;
        var line = lineOf(t);
        if (!t || !line) {
            return;
        }
        ev.preventDefault();
        ev.stopImmediatePropagation();
        var min = parseInt(line.getAttribute('data-min'), 10) || 1;
        var step = parseInt(line.getAttribute('data-step'), 10) || 1;
        var cur = current(line);
        if (t.classList.contains('js_delete_product')) {
            setQty(line, 0);
        } else if (t.querySelector('.fa-minus')) {
            var down = cur - step;
            if (down < min) {
                if (window.dkToast && window.dkRuleMsg) {
                    window.dkToast(window.dkRuleMsg({ min: min, step: step }) + ' Para quitarlo, usa "Quitar".');
                }
                return;
            }
            schedule(line, down);
        } else {
            schedule(line, cur ? cur + step : min);
        }
    }, true);

    document.addEventListener('change', function (ev) {
        if (!inDkh()) {
            return;
        }
        var input = ev.target;
        var line = input && input.classList && input.classList.contains('js_quantity') ? lineOf(input) : null;
        if (!line) {
            return;
        }
        ev.stopImmediatePropagation();
        var n = parseInt(input.value, 10);
        if (n > 0) {
            var cmin = parseInt(line.getAttribute('data-min'), 10) || 1;
            var cstep = parseInt(line.getAttribute('data-step'), 10) || 1;
            var fixed = Math.max(cmin, Math.floor((n + Math.floor(cstep / 2)) / cstep) * cstep);
            if (fixed !== n && window.dkToast && window.dkRuleMsg) {
                window.dkToast(window.dkRuleMsg({ min: cmin, step: cstep }) + ' Quedó en ' + fixed + '.');
            }
            n = fixed;
        }
        schedule(line, n > 0 ? n : 0);
    }, true);

    document.addEventListener('focusin', function (ev) {
        var input = ev.target;
        if (inDkh() && input && input.classList && input.classList.contains('js_quantity') && lineOf(input)) {
            input.select();
        }
    });
})();
