/* Buscador del encabezado: lista de sugerencias propia. Reemplaza el autocompletado nativo de
 * Odoo, que se trababa al borrar y no cargaba dentro de la tienda/ficha/carrito. Los eventos
 * del campo se atienden en fase de captura y se frenan ahí, así el widget nativo (si llega a
 * iniciarse) no interviene. Habla con /shop/dk/suggest (controllers/shop_suggest.py). */
(function () {
    'use strict';

    var DEBOUNCE_MS = 220;
    var MIN_CHARS = 2;
    var timer = null;
    var seq = 0;
    var cache = {};

    // Campo propio del encabezado + los buscadores nativos que Odoo deja en el menú del celular
    // (las tres líneas) y en el modal de la lupa: todos se atienden igual.
    var FIELD_SEL = '.dk-hsearch-input, #top_menu_collapse_mobile .oe_search_box, #o_search_modal .oe_search_box';

    function isField(el) {
        return !!(el && el.matches && el.matches(FIELD_SEL));
    }

    function formOf(input) {
        return input.closest('form');
    }

    function listFor(input) {
        var form = formOf(input);
        var list = form.querySelector('.dk-sug');
        if (!list) {
            list = document.createElement('div');
            list.className = 'dk-sug';
            list.setAttribute('role', 'listbox');
            list.hidden = true;
            form.appendChild(list);
        }
        return list;
    }

    function hide(input) {
        var list = formOf(input).querySelector('.dk-sug');
        if (list) {
            list.hidden = true;
        }
    }

    function item(it) {
        var a = document.createElement('a');
        a.className = 'dk-sug-item';
        a.href = it.url;
        a.setAttribute('role', 'option');
        var img = document.createElement('img');
        img.src = it.image;
        img.alt = '';
        img.loading = 'lazy';
        var name = document.createElement('span');
        name.className = 'dk-sug-name';
        name.textContent = it.name;
        var price = document.createElement('span');
        price.className = 'dk-sug-price';
        price.textContent = it.price;
        a.appendChild(img);
        a.appendChild(name);
        a.appendChild(price);
        return a;
    }

    function render(input, term, data) {
        var list = listFor(input);
        list.textContent = '';
        if (!data.items.length) {
            var none = document.createElement('div');
            none.className = 'dk-sug-none';
            none.textContent = 'No encontramos «' + term + '». Prueba con otra palabra.';
            list.appendChild(none);
        } else {
            data.items.forEach(function (it) {
                list.appendChild(item(it));
            });
            var more = document.createElement('a');
            more.className = 'dk-sug-all';
            more.href = '/shop?search=' + encodeURIComponent(term);
            more.textContent = 'Ver los ' + data.total + ' resultados de «' + term + '»';
            list.appendChild(more);
        }
        list.hidden = false;
    }

    function fetchSuggestions(input) {
        var term = input.value.trim();
        if (term.length < MIN_CHARS) {
            hide(input);
            return;
        }
        if (cache[term]) {
            render(input, term, cache[term]);
            return;
        }
        var mine = ++seq;
        fetch('/shop/dk/suggest', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { term: term } })
        }).then(function (r) {
            return r.json();
        }).then(function (res) {
            var d = res && res.result;
            if (!d || mine !== seq || input.value.trim() !== term) {
                return; // llegó tarde: ya escribió otra cosa
            }
            cache[term] = d;
            render(input, term, d);
        }).catch(function () {
            hide(input);
        });
    }

    function stop(ev) {
        ev.stopImmediatePropagation();
    }

    document.addEventListener('input', function (ev) {
        if (!isField(ev.target)) {
            return;
        }
        stop(ev);
        clearTimeout(timer);
        timer = setTimeout(function () {
            fetchSuggestions(ev.target);
        }, DEBOUNCE_MS);
    }, true);

    document.addEventListener('focus', function (ev) {
        if (!isField(ev.target)) {
            return;
        }
        stop(ev);
        var list = formOf(ev.target).querySelector('.dk-sug');
        if (list && list.children.length && ev.target.value.trim().length >= MIN_CHARS) {
            list.hidden = false;
        }
    }, true);

    document.addEventListener('keyup', function (ev) {
        if (isField(ev.target)) {
            stop(ev);
        }
    }, true);

    document.addEventListener('keydown', function (ev) {
        var input = ev.target;
        if (!isField(input)) {
            return;
        }
        stop(ev); // nunca se cancela Retroceso/Suprimir: el campo se comporta normal
        var list = formOf(input).querySelector('.dk-sug');
        var open = list && !list.hidden;
        if (ev.key === 'Escape') {
            hide(input);
            return;
        }
        if (!open || (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp' && ev.key !== 'Enter')) {
            return;
        }
        var links = Array.prototype.slice.call(list.querySelectorAll('a'));
        var cur = links.findIndex(function (a) { return a.classList.contains('dk-act'); });
        if (ev.key === 'Enter') {
            if (cur >= 0) {
                ev.preventDefault();
                window.location.href = links[cur].href;
            }
            return; // sin selección: se envía el formulario normal (/shop?search=...)
        }
        ev.preventDefault();
        if (cur >= 0) {
            links[cur].classList.remove('dk-act');
        }
        var next = ev.key === 'ArrowDown' ? cur + 1 : cur - 1;
        next = (next + links.length) % links.length;
        links[next].classList.add('dk-act');
    }, true);

    document.addEventListener('click', function (ev) {
        all('form:has(.dk-sug)').forEach(function (form) {
            if (!form.contains(ev.target)) {
                var list = form.querySelector('.dk-sug');
                if (list) {
                    list.hidden = true;
                }
            }
        });
    });

    function all(sel) {
        return Array.prototype.slice.call(document.querySelectorAll(sel));
    }
})();
