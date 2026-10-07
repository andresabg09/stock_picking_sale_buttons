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

    // Qué hacer con lo leído: un enlace de esta misma tienda se abre; lo demás se busca como código.
    function onCode(raw) {
        var code = (raw || '').trim();
        if (!code || busy) {
            return;
        }
        busy = true;
        stopCamera();
        setMsg('Código leído: ' + code);
        var url = '/shop?search=' + encodeURIComponent(code);
        if (/^https?:\/\//i.test(code)) {
            try {
                var u = new URL(code);
                if (u.origin === window.location.origin) {
                    url = u.pathname + u.search;
                }
            } catch (e) { /* se busca como texto */ }
        }
        window.location.href = url;
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
