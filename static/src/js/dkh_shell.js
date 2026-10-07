/* Versión H — encabezado: menú del celular/tablet y ventana del escáner.
 * JS plano (sin módulos de Odoo), igual que header_search.js. No hace nada si la página no
 * trae el encabezado H (clase `dkh` ausente). */
(function () {
    'use strict';

    var lastFocus = null;
    var stream = null;
    var timer = null;
    var detector = null;
    var zxingReader = null;
    var busy = false;
    var FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'itf', 'qr_code'];

    function setMsg(text) {
        var m = byId('dkh-scan-msg');
        if (m) {
            m.textContent = text;
        }
    }

    // Qué hacer con lo leído: un enlace de esta misma tienda se abre; un código de barras se
    // agrega al pedido (cantidad mínima) y la cámara sigue lista para el siguiente.
    function onCode(raw) {
        var code = (raw || '').trim();
        if (!code || busy) {
            return;
        }
        busy = true;
        if (/^https?:\/\//i.test(code)) {
            try {
                var u = new URL(code);
                if (u.origin === window.location.origin) {
                    stopCamera();
                    window.location.href = u.pathname + u.search;
                    return;
                }
            } catch (e) { /* se trata como código */ }
        }
        setMsg('Buscando ' + code + '…');
        fetch('/shop/dk/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { code: code } })
        }).then(function (r) { return r.json(); }).then(function (d) {
            var res = d && d.result;
            if (res && res.found) {
                setMsg('✓ ' + res.name + ' · ' + res.qty + ' en tu pedido');
                setCartCount(res.cart_lines);
            } else if (res && res.many) {
                stopCamera();
                window.location.href = res.url;
                return;
            } else {
                setMsg('No encontramos el código ' + code);
            }
            setTimeout(function () { busy = false; setMsg('Apunta al siguiente código'); }, 1800);
        }).catch(function () {
            setMsg('No se pudo agregar. Intenta de nuevo.');
            setTimeout(function () { busy = false; }, 1800);
        });
    }

    function stopCamera() {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
        if (zxingReader) {
            try { zxingReader.reset(); } catch (e) { /* nada */ }
            zxingReader = null;
        }
        if (stream) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            stream = null;
        }
        var v = byId('dkh-video');
        if (v) {
            v.srcObject = null;
        }
    }

    function loadZxing(cb) {
        if (window.ZXing) {
            return cb();
        }
        var s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/@zxing/library@0.21.3/umd/index.min.js';
        s.onload = cb;
        s.onerror = function () { setMsg('No se pudo cargar el lector. Revisa tu conexión.'); };
        document.head.appendChild(s);
    }

    function startCamera() {
        busy = false;
        var video = byId('dkh-video');
        if (!video) {
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setMsg('Este navegador no permite usar la cámara aquí.');
            return;
        }
        setMsg('Abriendo la cámara…');
        navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
            .then(function (st) {
                stream = st;
                video.srcObject = st;
                var p = video.play();
                if (p && p.catch) { p.catch(function () { /* autoplay */ }); }
                setMsg('Apunta al código de barras o QR');
                if ('BarcodeDetector' in window) {
                    detector = new window.BarcodeDetector({ formats: FORMATS });
                    timer = setInterval(function () {
                        if (busy || video.readyState < 2) {
                            return;
                        }
                        detector.detect(video).then(function (found) {
                            if (found && found.length) {
                                onCode(found[0].rawValue);
                            }
                        }).catch(function () { /* fotograma sin código */ });
                    }, 250);
                } else {
                    loadZxing(function () {
                        if (!stream) {
                            return;
                        }
                        var Z = window.ZXing;
                        var hints = new Map();
                        hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, [
                            Z.BarcodeFormat.EAN_13, Z.BarcodeFormat.EAN_8, Z.BarcodeFormat.UPC_A,
                            Z.BarcodeFormat.UPC_E, Z.BarcodeFormat.CODE_128, Z.BarcodeFormat.CODE_39,
                            Z.BarcodeFormat.ITF, Z.BarcodeFormat.QR_CODE]);
                        zxingReader = new Z.BrowserMultiFormatReader(hints);
                        zxingReader.decodeFromVideoElementContinuously
                            ? zxingReader.decodeFromVideoElementContinuously(video, function (res) {
                                if (res) { onCode(res.getText()); }
                            })
                            : zxingReader.decodeFromVideoElement(video, function (res) {
                                if (res) { onCode(res.getText()); }
                            });
                    });
                }
            })
            .catch(function (err) {
                var name = err && err.name;
                if (name === 'NotAllowedError' || name === 'SecurityError') {
                    setMsg('Permite el acceso a la cámara en tu navegador y vuelve a intentar.');
                } else if (name === 'NotFoundError') {
                    setMsg('No se encontró ninguna cámara.');
                } else {
                    setMsg('No se pudo abrir la cámara.');
                }
            });
    }

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
        startCamera();
    }

    function closeScan() {
        var box = byId('dkh-scan');
        if (!box || box.hidden) {
            return;
        }
        box.hidden = true;
        stopCamera();
        document.body.classList.remove('dkh-lock');
        if (lastFocus && lastFocus.focus) {
            lastFocus.focus();
        }
    }

    function setMore(open) {
        var more = byId('dkh-more');
        var btn = document.querySelector('[data-dkh-more]');
        if (!more) {
            return;
        }
        more.hidden = !open;
        if (btn) {
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        }
    }

    function toggleMore() {
        var more = byId('dkh-more');
        setMore(!!(more && more.hidden));
    }

    document.addEventListener('click', function (ev) {
        var t = ev.target.closest ? ev.target.closest('[data-dkh-scan], [data-dkh-more], .dkh-more, .dkh-scrim') : null;
        if (!t) {
            return;
        }
        if (t.matches('[data-dkh-scan="open"]')) {
            ev.preventDefault();
            openScan();
        } else if (t.matches('[data-dkh-scan="close"]')) {
            ev.preventDefault();
            closeScan();
        } else if (t.matches('[data-dkh-more]')) {
            ev.preventDefault();
            toggleMore();
        } else if (t.classList.contains('dkh-more') && ev.target === t) {
            setMore(false); // clic en el fondo oscuro
        } else if (t.classList.contains('dkh-scrim') && ev.target === t) {
            closeScan(); // clic en el fondo oscuro
        }
    });

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') {
            setMore(false);
            closeScan();
        }
    });

    // Carrusel del banner principal: avanza solo cada 6 s; se detiene al tocar/pasar el mouse.
    function initHero() {
        var tr = document.querySelector('.dkh-hero-track');
        if (!tr || !tr.children.length || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) {
            return;
        }
        var idx = 0;
        var hold = false;
        tr.addEventListener('mouseenter', function () { hold = true; });
        tr.addEventListener('mouseleave', function () { hold = false; });
        tr.addEventListener('touchstart', function () { hold = true; }, { passive: true });
        tr.addEventListener('touchend', function () { setTimeout(function () { hold = false; }, 6000); }, { passive: true });
        tr.addEventListener('scroll', function () {
            idx = Math.round(tr.scrollLeft / (tr.clientWidth || 1));
        }, { passive: true });
        setInterval(function () {
            if (hold || document.hidden) {
                return;
            }
            idx = (idx + 1) % tr.children.length;
            tr.scrollTo({ left: idx * tr.clientWidth, behavior: 'smooth' });
        }, 6000);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initHero);
    } else {
        initHero();
    }

    // Categorías deslizables (celular/tablet): al elegir una, la fila queda con esa categoría al
    // principio, sin tener que volver a deslizar desde el inicio.
    function revealActiveChip() {
        var rows = document.querySelectorAll('.dk-chips');
        Array.prototype.forEach.call(rows, function (row) {
            var act = row.querySelector('.act');
            if (act && row.scrollWidth > row.clientWidth) {
                row.scrollLeft = Math.max(0, act.getBoundingClientRect().left - row.getBoundingClientRect().left + row.scrollLeft - 12);
            }
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', revealActiveChip);
    } else {
        revealActiveChip();
    }
    window.addEventListener('load', revealActiveChip);

    // ---- Encabezado fijo: se esconde al bajar y reaparece al subir ----
    function setCartCount(n) {
        var el = document.querySelector('.dkh-cart-count');
        if (!el || n === undefined || n === null) {
            return;
        }
        el.textContent = String(n);
        el.hidden = !n;
    }
    window.dkSetCartCount = setCartCount;

    function bar() {
        return document.querySelector('.dkh-bar');
    }

    function initBar() {
        var b = bar();
        if (!b) {
            return;
        }
        var sc = document.getElementById('wrapwrap');
        var last = 0;
        function pos() {
            return Math.max((sc && sc.scrollTop) || 0, window.pageYOffset || 0);
        }
        function onScroll() {
            var y = pos();
            var d = y - last;
            if (y <= 80) {
                b.classList.remove('is-hidden');
            } else if (d > 8) {
                b.classList.add('is-hidden');
            } else if (d < -8) {
                b.classList.remove('is-hidden');
            }
            last = y;
        }
        window.addEventListener('scroll', onScroll, { passive: true });
        if (sc) {
            sc.addEventListener('scroll', onScroll, { passive: true });
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBar);
    } else {
        initBar();
    }

    // ---- El producto vuela hacia el carrito al agregarlo ----
    window.dkFly = function (src) {
        try {
            if (!document.body.classList.contains('dkh') || !src) {
                return;
            }
            if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                return;
            }
            var host = src.closest ? src.closest('.dk-card, .dkh-row, .qo-sug, .dk-pbox') : null;
            var img = (host && host.querySelector('img')) || document.querySelector('#product_detail img');
            var cart = document.querySelector('.dkh-cart');
            var r = img && img.getBoundingClientRect();
            if (!img || !cart || !r.width) {
                return;
            }
            var b = bar();
            if (b) {
                b.classList.remove('is-hidden'); // se muestra el carrito para ver adónde llega
            }
            var ghost = img.cloneNode(false);
            ghost.removeAttribute('id');
            ghost.className = 'dkh-fly';
            ghost.style.cssText = 'left:' + r.left + 'px;top:' + r.top + 'px;width:' + r.width + 'px;height:' + r.height + 'px;';
            document.body.appendChild(ghost);
            var cr = cart.getBoundingClientRect();
            var tx = cr.left + cr.width / 2;
            var ty = Math.max(cr.top + cr.height / 2, 30);
            var dx = tx - (r.left + r.width / 2);
            var dy = ty - (r.top + r.height / 2);
            var anim = ghost.animate([
                { transform: 'translate(0,0) scale(1)', opacity: 1 },
                { transform: 'translate(' + (dx * 0.55) + 'px,' + (dy * 0.55 - 36) + 'px) scale(.5)', opacity: .95, offset: .55 },
                { transform: 'translate(' + dx + 'px,' + dy + 'px) scale(.1)', opacity: .25 }
            ], { duration: 700, easing: 'cubic-bezier(.5,0,.2,1)' });
            anim.onfinish = function () {
                ghost.remove();
                cart.classList.remove('bump');
                void cart.offsetWidth;
                cart.classList.add('bump');
            };
        } catch (e) { /* la animación nunca debe estorbar */ }
    };
})();
