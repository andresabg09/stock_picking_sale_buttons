/* Tienda: cantidad "viva" en las tarjetas. Lo que el cliente escribe (o suma con +/−)
 * queda en el carrito al momento — sin botón de confirmar. Habla con
 * /shop/dk/set_qty (controllers/shop_live_cart.py) y actualiza el contador del
 * encabezado y la píldora flotante. JS plano (sin módulos de Odoo) a propósito. */
(function () {
    'use strict';

    var DEBOUNCE_MS = 350;
    var timers = {};
    var seq = {};
    var toastTimer = null;

    function all(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function boxesFor(pid) {
        return all('.dk-buy[data-product-id="' + pid + '"]');
    }

    function currentQty(box) {
        if (box.dataset.state !== 'in') {
            return 0;
        }
        var n = parseInt(box.querySelector('.dk-q').value, 10);
        return isNaN(n) || n < 0 ? 0 : n;
    }

    function setInLine(box, total) {
        var el = box.querySelector('.dk-in');
        el.textContent = '';
        var icon = document.createElement('i');
        icon.className = 'fa fa-check';
        icon.setAttribute('aria-hidden', 'true');
        el.appendChild(icon);
        el.appendChild(document.createTextNode(' En tu carrito' + (total ? ' · ' + total : '')));
    }

    function render(box, qty, total) {
        var input = box.querySelector('.dk-q');
        box.dataset.state = qty > 0 ? 'in' : 'out';
        all('.dk-pre', box).forEach(function (b) {
            b.classList.toggle('act', qty > 0 && parseInt(b.dataset.qty, 10) === qty);
        });
        if (qty > 0) {
            if (document.activeElement !== input) {
                input.value = String(qty);
            }
            setInLine(box, total || '');
        } else {
            input.value = '1';
        }
    }

    function toast(msg) {
        var el = document.getElementById('dk-toast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'dk-toast';
            el.className = 'dk-toast';
            el.setAttribute('role', 'status');
            document.body.appendChild(el);
        }
        el.textContent = msg;
        el.classList.add('dk-show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            el.classList.remove('dk-show');
        }, 3500);
    }

    function updateCart(d) {
        all('.my_cart_quantity').forEach(function (el) {
            el.textContent = String(d.cart_quantity);
            el.classList.toggle('d-none', !d.cart_quantity);
        });
        all('.dk-actions').forEach(function (el) {
            el.classList.toggle('d-none', !d.cart_lines);
        });
        var pill = document.getElementById('dk-pill');
        if (pill) {
            var set = function (cls, text) {
                var n = pill.querySelector(cls);
                if (n) {
                    n.textContent = text;
                }
            };
            var lines = d.cart_lines;
            var units = Math.round(d.cart_quantity);
            set('.dk-pill-lines', String(lines));
            set('.dk-pill-word', lines === 1 ? 'producto' : 'productos');
            set('.dk-pill-units', String(units));
            set('.dk-pill-uword', units === 1 ? 'unidad' : 'unidades');
            pill.classList.toggle('d-none', !d.cart_lines);
        }
    }

    function send(pid, qty) {
        seq[pid] = (seq[pid] || 0) + 1;
        var mine = seq[pid];
        var boxes = boxesFor(pid);
        boxes.forEach(function (b) { b.classList.add('dk-busy'); });
        return fetch('/shop/dk/set_qty', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { product_id: pid, qty: qty } })
        }).then(function (r) {
            return r.json();
        }).then(function (res) {
            if (mine !== seq[pid]) {
                return; // llegó una respuesta más nueva
            }
            var d = res && res.result;
            if (!d || d.error) {
                throw new Error((d && d.error) || 'No se pudo actualizar el carrito.');
            }
            boxes.forEach(function (b) { render(b, d.qty, d.line_total); });
            updateCart(d);
            if (qty > 0 && d.qty < qty) {
                toast(d.qty > 0
                    ? 'Solo hay ' + d.qty + ' disponibles de este producto.'
                    : 'Este producto no tiene disponibilidad por ahora.');
            }
        }).catch(function (err) {
            if (mine !== seq[pid]) {
                return;
            }
            boxes.forEach(function (b) {
                var last = parseInt(b.dataset.qty, 10) || 0;
                render(b, last, '');
            });
            toast(err.message || 'No se pudo actualizar el carrito. Intenta de nuevo.');
        }).then(function () {
            if (mine === seq[pid]) {
                boxes.forEach(function (b) {
                    b.classList.remove('dk-busy');
                    b.dataset.qty = b.dataset.state === 'in' ? String(currentQty(b)) : '0';
                });
            }
        });
    }

    function change(box, qty) {
        var pid = box.dataset.productId;
        qty = Math.max(0, Math.min(qty, 99999));
        boxesFor(pid).forEach(function (b) { render(b, qty, ''); });
        clearTimeout(timers[pid]);
        timers[pid] = setTimeout(function () { send(pid, qty); }, DEBOUNCE_MS);
    }

    function initPresets() {
        all('.dk-buy[data-state="in"]').forEach(function (b) {
            var q = parseInt(b.dataset.qty, 10) || 0;
            all('.dk-pre', b).forEach(function (p) {
                p.classList.toggle('act', parseInt(p.dataset.qty, 10) === q);
            });
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPresets);
    } else {
        initPresets();
    }

    document.addEventListener('click', function (ev) {
        var btn = ev.target.closest ? ev.target.closest('.dk-add, .dk-minus, .dk-plus, .dk-pre') : null;
        var box = btn && btn.closest('.dk-buy');
        if (!box) {
            return;
        }
        ev.preventDefault();
        var cur = currentQty(box);
        var next;
        if (btn.classList.contains('dk-pre')) {
            next = parseInt(btn.dataset.qty, 10) || 1;
        } else if (btn.classList.contains('dk-add')) {
            next = 1;
        } else if (btn.classList.contains('dk-plus')) {
            next = cur + 1;
        } else {
            next = Math.max(0, cur - 1);
        }
        change(box, next);
    });

    document.addEventListener('change', function (ev) {
        var input = ev.target;
        var box = input.classList && input.classList.contains('dk-q') ? input.closest('.dk-buy') : null;
        if (!box) {
            return;
        }
        var n = parseInt(String(input.value).replace(/[^0-9]/g, ''), 10);
        if (isNaN(n)) {
            input.value = String(currentQty(box) || 1);
            return;
        }
        change(box, n);
    });

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && ev.target.classList && ev.target.classList.contains('dk-q')) {
            ev.preventDefault(); // la tarjeta es un <form>: no enviarlo
            ev.target.blur();
        }
    });
})();
