/** @odoo-module **/

// Animación del menú de apps (web_responsive): ola diagonal + luciérnagas doradas.
// Autónomo: solo observa el DOM (.o_grid_apps_menu / .app-menu-container); no importa nada de
// web_responsive, así que si ese módulo no está instalado simplemente no hace nada.
// Apagar en un navegador: localStorage.setItem("dkw_off", "1")  (encender: removeItem).
// Diseño aprobado por Andrés (2026-10-10): lienzo "Animación del menú de apps — Propuesta".

const BOX = "app-menu-container";
const rects = new WeakMap(); // caja del menú -> rectángulo medido al abrir (para animar el cierre)
let current = null; // animación de apertura en curso
let observed = null;

function disabled() {
    try {
        return window.localStorage.getItem("dkw_off") === "1";
    } catch (e) {
        return false;
    }
}

function reduced() {
    try {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (e) {
        return false;
    }
}

// Ajustes por tamaño de pantalla: teléfono < 768, tablet < 1200, PC desde 1200
function cfg() {
    const w = window.innerWidth;
    if (w < 768) {
        return { N: 36, amp: [34, 30, 26], lam: [200, 240, 280], flies: 10, speed: 0.72, core: 1.5 };
    }
    if (w < 1200) {
        return { N: 48, amp: [52, 46, 40], lam: [300, 350, 400], flies: 18, speed: 0.88, core: 1.8 };
    }
    return { N: 56, amp: [70, 62, 54], lam: [360, 420, 480], flies: 26, speed: 1, core: 1.8 };
}

function ease(k) {
    return k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
}

// Frente de la ola: línea diagonal (x + y = F) con ondulación suave que viaja.
function waveClip(p, extra, amp, lam, ph, W, H, N) {
    if (p <= 0.001) {
        return "polygon(0px 0px, 0px 0px, 0px 0px)";
    }
    const raw = p * (W + H + 2 * amp + extra);
    const a = amp * Math.min(1, raw / (4 * amp)); // la ondulación crece con la ola: sin picos al nacer
    const F = raw - a;
    // La línea del frente se extiende más allá de la caja por ambos lados (u de -0.4 a 1.4) y se
    // cierra por fuera de ella: así no quedan franjas finas en los bordes.
    // Un punto cada ~14 px de borde (con tope según el dispositivo) para que la curva se vea suave.
    const n = Math.min(N * 3, Math.max(40, Math.ceil((1.8 * F * 1.4142) / 14)));
    const pts = ["-2000px -2000px"];
    for (let i = 0; i <= n; i++) {
        const u = -0.4 + (1.8 * i) / n;
        const s = u * F * 1.4142;
        const w =
            a *
            (0.72 * Math.sin((s / lam) * 6.2832 - ph) +
                0.28 * Math.sin((s / (lam * 0.43)) * 6.2832 - ph * 1.7));
        pts.push((F * u + w / 2).toFixed(1) + "px " + (F * (1 - u) + w / 2).toFixed(1) + "px");
    }
    return "polygon(" + pts.join(",") + ")";
}

function setClip(el, poly) {
    el.style.clipPath = poly;
    el.style.webkitClipPath = poly;
}

function applyWave(st, p) {
    const W = st.rect.width;
    const H = st.rect.height;
    const c = st.c;
    const ph = p * 11;
    setClip(st.box, waveClip(p, 0, c.amp[2], c.lam[2], ph + 2.6, W, H, c.N));
    setClip(st.mid, waveClip(p, 75, c.amp[1], c.lam[1], ph + 1.3, W, H, c.N));
    setClip(st.back, waveClip(p, 150, c.amp[0], c.lam[0], ph, W, H, c.N));
}

// Capas de color de la ola (el color de la barra superior, y un tono medio)
function makeLayer(cls, rect, color, mix) {
    const el = document.createElement("div");
    el.className = "dkw-layer " + cls;
    el.setAttribute("aria-hidden", "true");
    el.style.cssText =
        "top:" + rect.top + "px;left:" + rect.left + "px;width:" + rect.width + "px;height:" + rect.height + "px;";
    el.style.background = color;
    if (mix) {
        el.style.background = "color-mix(in srgb, " + color + " 52%, white)"; // si no lo soporta, queda el color base
    }
    document.body.appendChild(el);
    return el;
}

function navColor() {
    try {
        const n = document.querySelector(".o_main_navbar");
        if (n) {
            const c = window.getComputedStyle(n).backgroundColor;
            if (c && c !== "rgba(0, 0, 0, 0)" && c !== "transparent") {
                return c;
            }
        }
    } catch (e) {
        /* se usa el color por defecto */
    }
    return "#71639e";
}

function makeLayers(st) {
    const col = navColor();
    st.back = makeLayer("dkw-back", st.rect, col, false);
    st.mid = makeLayer("dkw-mid", st.rect, col, true);
}

function removeLayers(st) {
    [st.back, st.mid].forEach((el) => el && el.remove());
    st.back = st.mid = null;
}

function later(st, fn, ms) {
    st.timers.push(setTimeout(fn, ms));
}

function tween(st, from, to, ms, done) {
    const t0 = performance.now();
    const step = (now) => {
        if (st.dead) {
            return;
        }
        const k = Math.min(1, (now - t0) / ms);
        st.p = from + (to - from) * ease(k);
        applyWave(st, st.p);
        if (k < 1) {
            st.raf = requestAnimationFrame(step);
        } else if (done) {
            done();
        }
    };
    st.raf = requestAnimationFrame(step);
}

function cancel(st) {
    st.dead = true;
    cancelAnimationFrame(st.raf);
    st.timers.forEach(clearTimeout);
    removeLayers(st);
}

// Iconos y buscador: aparecen en cascada cuando la ola ya pasó
function hideContent(st) {
    st.items = [];
    st.blocks = [];
    Array.from(st.box.children).forEach((ch) => {
        if (ch.classList.contains("dkw-flies")) {
            return;
        }
        if (ch.classList.contains("o-app-menu-list")) {
            st.items.push(...Array.from(ch.children));
        } else {
            st.blocks.push(ch);
        }
    });
    st.items.forEach((el) => {
        el.style.opacity = "0";
        el.style.transform = "translateY(14px) scale(0.92)";
    });
    st.blocks.forEach((el) => {
        el.style.opacity = "0";
    });
}

function revealContent(st) {
    st.items.forEach((el, i) => {
        const d = 60 + Math.min(i, 16) * 40;
        el.style.transition =
            "opacity .5s ease " + d + "ms, transform .6s cubic-bezier(.2,.8,.2,1) " + d + "ms";
        el.style.opacity = "1";
        el.style.transform = "none";
    });
    st.blocks.forEach((el) => {
        el.style.transition = "opacity .5s ease";
        el.style.opacity = "1";
    });
}

function clearContent(st) {
    st.items.concat(st.blocks).forEach((el) => {
        el.style.opacity = "";
        el.style.transform = "";
        el.style.transition = "";
    });
}

// Luciérnagas doradas: luz suave que deriva despacio y "respira" (canvas liviano, detrás de los iconos)
function startFlies(st) {
    const rect = st.rect;
    const c = st.c;
    const cv = document.createElement("canvas");
    cv.className = "dkw-flies";
    cv.setAttribute("aria-hidden", "true");
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    cv.width = Math.max(1, Math.round(rect.width * dpr));
    cv.height = Math.max(1, Math.round(rect.height * dpr));
    cv.style.cssText =
        "top:" + rect.top + "px;left:" + rect.left + "px;width:" + rect.width + "px;height:" + rect.height + "px;";
    st.box.insertBefore(cv, st.box.firstChild);
    const ctx = cv.getContext("2d");
    if (!ctx) {
        cv.remove();
        return;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Sprite de la luz (se dibuja una vez)
    const sp = document.createElement("canvas");
    sp.width = sp.height = 64;
    const sctx = sp.getContext("2d");
    const g = sctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,244,204,1)");
    g.addColorStop(0.12, "rgba(255,211,107,1)");
    g.addColorStop(0.3, "rgba(240,168,31,0.55)");
    g.addColorStop(0.68, "rgba(240,168,31,0)");
    sctx.fillStyle = g;
    sctx.fillRect(0, 0, 64, 64);

    const fr = (x) => {
        const v = Math.sin(x) * 43758.5453;
        return v - Math.floor(v);
    };
    const flies = [];
    const W = rect.width;
    const H = rect.height;
    const sc = W / 1280 + 0.3;
    for (let i = 0; i < c.flies; i++) {
        flies.push({
            bx: fr(i * 1.7 + 1) * (W - 40) + 20,
            by: fr(i * 2.3 + 5) * (H - 40) + 20,
            R: (c.core + fr(i * 3.1 + 2) * 1.8) * 7,
            sx: 0.25 + fr(i * 4.7) * 0.3,
            sy: 0.2 + fr(i * 5.3) * 0.3,
            ax: 30 + fr(i * 6.1) * 60 * sc,
            ay: 24 + fr(i * 7.7) * 50 * sc,
            sg: 0.9 + fr(i * 8.9) * 1.1,
            i: i,
        });
    }
    const t0 = performance.now();
    let fl = 0;
    const tick = (now) => {
        if (!cv.isConnected) {
            return; // el menú se cerró: la animación se detiene sola
        }
        const t = (now - t0) / 1000;
        fl += ((st.fliesOn ? 1 : 0) - fl) * 0.07;
        ctx.clearRect(0, 0, W, H);
        if (fl > 0.003) {
            flies.forEach((f) => {
                const x = f.bx + Math.sin(t * f.sx + f.i * 1.9) * f.ax;
                const y = f.by + Math.cos(t * f.sy + f.i * 2.7) * f.ay;
                const glow = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(t * f.sg + f.i * 3.3));
                ctx.globalAlpha = glow * fl;
                ctx.drawImage(sp, x - f.R, y - f.R, f.R * 2, f.R * 2);
            });
            ctx.globalAlpha = 1;
        }
        requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
}

function onOpen(box) {
    if (disabled()) {
        return;
    }
    if (current) {
        cancel(current);
        current = null;
    }
    const rect = box.getBoundingClientRect();
    if (rect.width < 50 || rect.height < 50) {
        return;
    }
    rects.set(box, { top: rect.top, left: rect.left, width: rect.width, height: rect.height });
    if (reduced()) {
        box.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
        return;
    }
    const c = cfg();
    const ms = Math.round(1000 * c.speed);
    const st = {
        box: box,
        rect: rects.get(box),
        c: c,
        p: 0,
        raf: 0,
        dead: false,
        timers: [],
        fliesOn: false,
        items: [],
        blocks: [],
    };
    current = st;
    makeLayers(st);
    applyWave(st, 0); // se oculta antes del primer dibujo: sin parpadeo
    startFlies(st);
    hideContent(st);
    later(st, () => {
        revealContent(st);
        st.fliesOn = true;
    }, ms * 0.5);
    later(st, () => clearContent(st), ms * 0.5 + 1500);
    tween(st, 0, 1, ms, () => {
        box.style.clipPath = "";
        box.style.webkitClipPath = "";
        removeLayers(st);
        st.dead = true;
        if (current === st) {
            current = null;
        }
    });
}

// Al cerrarse, Odoo quita el menú de golpe. Lo recuperamos (ya está desconectado) y lo
// usamos de "fantasma" mientras la ola se retira y deja ver el módulo elegido.
function onClose(box, root) {
    const rect = rects.get(box);
    if (!rect || disabled() || reduced()) {
        return;
    }
    let p0 = 1;
    if (current && current.box === box) {
        p0 = current.p;
        cancel(current);
        current = null;
    }
    const cv = box.querySelector("canvas.dkw-flies");
    if (cv) {
        cv.remove();
    }
    const c = cfg();
    const wrap = document.createElement("div");
    wrap.className = "dkw-ghost o_grid_apps_menu";
    const theme = root && root.getAttribute("data-theme");
    if (theme) {
        wrap.setAttribute("data-theme", theme);
    }
    wrap.style.cssText =
        "top:" + rect.top + "px;left:" + rect.left + "px;width:" + rect.width + "px;height:" + rect.height + "px;";
    document.body.appendChild(wrap);
    wrap.appendChild(box);
    box.style.setProperty("position", "absolute", "important");
    box.style.setProperty("top", "0", "important");
    box.style.setProperty("left", "0", "important");
    box.style.setProperty("width", "100%", "important");
    box.style.setProperty("height", "100%", "important");
    box.style.setProperty("max-height", "none", "important");
    box.style.pointerEvents = "none";

    const st = {
        box: box,
        rect: rect,
        c: c,
        p: p0,
        raf: 0,
        dead: false,
        timers: [],
    };
    makeLayers(st);
    applyWave(st, p0);
    const fade = p0 > 0.9 ? 160 : 0;
    if (fade) {
        Array.from(box.children).forEach((ch) => {
            ch.style.transition = "opacity .16s ease";
            ch.style.opacity = "0";
        });
    }
    later(st, () => {
        const ms = Math.max(350, Math.round(1000 * c.speed * 0.9 * Math.max(p0, 0.4)));
        tween(st, p0, 0, ms, () => {
            st.dead = true;
            removeLayers(st);
            wrap.remove();
        });
    }, fade);
}

const observer = new MutationObserver((records) => {
    for (const r of records) {
        for (const n of r.addedNodes) {
            if (n.nodeType === 1 && n.classList.contains(BOX)) {
                try {
                    onOpen(n);
                } catch (e) {
                    console.warn("menu_wave: apertura sin animación", e);
                }
            }
        }
        for (const n of r.removedNodes) {
            if (n.nodeType === 1 && n.classList.contains(BOX)) {
                try {
                    onClose(n, r.target);
                } catch (e) {
                    console.warn("menu_wave: cierre sin animación", e);
                }
            }
        }
    }
});

// El botón del menú vive dentro de la barra superior, que Odoo puede volver a dibujar:
// cada medio segundo se comprueba que seguimos observando el contenedor vigente.
function attach() {
    const root = document.querySelector(".o_grid_apps_menu:not(.dkw-ghost)");
    if (root && root !== observed) {
        observer.disconnect();
        observer.observe(root, { childList: true });
        observed = root;
    }
}

setInterval(attach, 500);
attach();
