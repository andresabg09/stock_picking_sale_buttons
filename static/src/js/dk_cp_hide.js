/** @odoo-module **/

/* ENTREGAS (formulario del traslado): la barra de arriba (guardar ☁️ / descartar, tuerca, atajos, flechas de
   página) se esconde al bajar y reaparece al subir, para poder guardar sin volver a subir 100 filas. Solo esa
   barra: el nombre del cliente, los botones tipo Validar y el resto del formulario no se tocan.
   Solo aplica a formularios que traen la clase `dk-picking-form` (ver views/stock_picking_views.xml).
   Se activa con el primer desplazamiento (`dk-cp-on` en `.o_form_view`); desde ahí la barra "flota" y se
   desliza hacia arriba o abajo (CSS en static/src/css/dk_picking_header.css). */
const lastTop = new WeakMap();
let ticking = false;
let pending = null;

function update(scroller) {
    const root = scroller.closest(".o_form_view");
    if (!root || !root.querySelector(".dk-picking-form")) {
        return;
    }
    const cp = root.querySelector(".o_control_panel");
    if (!cp) {
        return;
    }
    const top = scroller.scrollTop;
    const prev = lastTop.has(scroller) ? lastTop.get(scroller) : top;
    const delta = top - prev;
    if (!lastTop.has(scroller)) {
        lastTop.set(scroller, top);
    }
    if (top > 0 && !root.classList.contains("dk-cp-on")) {
        root.style.setProperty("--dk-cp-h", cp.offsetHeight + "px");
        root.style.setProperty("--dk-cp-top", (root.querySelector(".o_form_view_container") || scroller).getBoundingClientRect().top + "px");
        root.classList.add("dk-cp-on");
    }
    if (Math.abs(delta) >= 6) {
        lastTop.set(scroller, top);
        if (delta > 0 && top > 80) {
            root.classList.add("dk-cp-hidden");
        } else if (delta < 0) {
            root.classList.remove("dk-cp-hidden");
        }
    }
    if (top <= 40) {
        root.classList.remove("dk-cp-hidden");
    }
}

document.addEventListener(
    "scroll",
    (ev) => {
        const target = ev.target;
        if (!target || target === document || !target.classList) {
            return;
        }
        if (!target.classList.contains("o_content") && !target.classList.contains("o_form_view_container")) {
            return;
        }
        pending = target;
        if (!ticking) {
            ticking = true;
            requestAnimationFrame(() => {
                ticking = false;
                if (pending) {
                    update(pending);
                }
            });
        }
    },
    true
);
