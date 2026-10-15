/** @odoo-module **/

// Zoom "como en cualquier galería de fotos" para fotos y videos: pellizcar con dos dedos (acerca/aleja y mueve a la
// vez), doble toque o doble clic (acerca al punto tocado / vuelve), arrastrar con un dedo o con el mouse cuando está
// acercado, y la rueda del mouse en computadora. Se usa en la revisión de la cámara y en el visor de adjuntos del log.
//
//   const zoom = new DkZoom({ container, getTarget, getContent, isVideo, onChange, onSwipe });
//   zoom.attach(); ...; zoom.detach();
//
// container  = el área que recibe los dedos (la pantalla de la foto)
// getTarget  = el elemento al que se le aplica el transform
// getContent = el elemento cuya medida real se usa para no dejar salir la foto del cuadro (por defecto el target)
// isVideo    = con video solo se usan DOS dedos (con un dedo siguen funcionando los controles del video)
// onSwipe    = (dir) con un dedo y sin zoom, deslizar a los lados (-1 / 1)

const MIN_SCALE = 1;
const MAX_SCALE = 8;
const DOUBLE_TAP_SCALE = 3;
const TAP_MS = 320;
const TAP_PX = 28;

export class DkZoom {
    constructor({ container, getTarget, getContent, isVideo, onChange, onSwipe }) {
        this.container = container;
        this.getTarget = getTarget;
        this.getContent = getContent || getTarget;
        this.isVideo = isVideo || (() => false);
        this.onChange = onChange || (() => {});
        this.onSwipe = onSwipe || null;
        this.scale = 1;
        this.tx = 0;
        this.ty = 0;
        this.pointers = new Map();
        this.gesture = null;
        this.lastTap = null;
        this.blockClickUntil = 0;
        this.bound = {
            down: (ev) => this.onDown(ev),
            move: (ev) => this.onMove(ev),
            up: (ev) => this.onUp(ev),
            wheel: (ev) => this.onWheel(ev),
            click: (ev) => this.onClick(ev),
        };
    }

    attach() {
        const el = this.container;
        el.addEventListener("pointerdown", this.bound.down);
        el.addEventListener("pointermove", this.bound.move);
        el.addEventListener("pointerup", this.bound.up);
        el.addEventListener("pointercancel", this.bound.up);
        el.addEventListener("wheel", this.bound.wheel, { passive: false });
        el.addEventListener("click", this.bound.click, true); // fase de captura: antes que el "cerrar" de Odoo
    }

    detach() {
        const el = this.container;
        el.removeEventListener("pointerdown", this.bound.down);
        el.removeEventListener("pointermove", this.bound.move);
        el.removeEventListener("pointerup", this.bound.up);
        el.removeEventListener("pointercancel", this.bound.up);
        el.removeEventListener("wheel", this.bound.wheel);
        el.removeEventListener("click", this.bound.click, true);
        this.pointers.clear();
    }

    // ---- medidas y transform ----
    get box() {
        const r = this.container.getBoundingClientRect();
        return { left: r.left, top: r.top, w: r.width, h: r.height, cx: r.left + r.width / 2, cy: r.top + r.height / 2 };
    }

    // Tamaño real de la foto SIN zoom (offset* no cambia con el transform); si está girada 90°, se intercambian.
    contentSize() {
        const content = this.getContent();
        if (!content) {
            return { w: 0, h: 0 };
        }
        const angle = parseFloat(/rotate\((-?[\d.]+)deg\)/.exec(content.style.transform || "")?.[1] || 0);
        const swap = Math.round(angle / 90) % 2 !== 0;
        return swap
            ? { w: content.offsetHeight, h: content.offsetWidth }
            : { w: content.offsetWidth, h: content.offsetHeight };
    }

    clamp() {
        const box = this.box;
        const size = this.contentSize();
        const maxX = Math.max(0, (size.w * this.scale - box.w) / 2);
        const maxY = Math.max(0, (size.h * this.scale - box.h) / 2);
        this.tx = Math.min(maxX, Math.max(-maxX, this.tx));
        this.ty = Math.min(maxY, Math.max(-maxY, this.ty));
    }

    apply(animate = false) {
        const target = this.getTarget();
        if (!target) {
            return;
        }
        target.style.transition = animate ? "transform .2s ease" : "none";
        target.style.willChange = "transform";
        target.style.transform =
            this.scale === 1 && !this.tx && !this.ty ? "" : `translate(${this.tx}px, ${this.ty}px) scale(${this.scale})`;
        this.onChange(this.scale);
    }

    reset(animate = false) {
        this.scale = 1;
        this.tx = 0;
        this.ty = 0;
        this.pointers.clear();
        this.gesture = null;
        this.apply(animate);
    }

    // Cambia el zoom dejando fijo el punto (fx, fy) de la pantalla (por defecto, el centro).
    zoomTo(newScale, fx, fy, animate = true) {
        const box = this.box;
        const px = (fx ?? box.cx) - box.cx;
        const py = (fy ?? box.cy) - box.cy;
        const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, newScale));
        this.tx = px - ((px - this.tx) * s) / this.scale;
        this.ty = py - ((py - this.ty) * s) / this.scale;
        this.scale = s;
        if (s === 1) {
            this.tx = 0;
            this.ty = 0;
        }
        this.clamp();
        this.apply(animate);
    }

    zoomBy(factor, fx, fy) {
        this.zoomTo(this.scale * factor, fx, fy);
    }

    // ---- dedos y mouse ----
    pair() {
        const [a, b] = [...this.pointers.values()];
        return {
            d: Math.hypot(a.x - b.x, a.y - b.y) || 1,
            x: (a.x + b.x) / 2,
            y: (a.y + b.y) / 2,
        };
    }

    startGesture() {
        const box = this.box;
        if (this.pointers.size >= 2) {
            const p = this.pair();
            this.gesture = {
                type: "pinch",
                d0: p.d,
                s0: this.scale,
                tx0: this.tx,
                ty0: this.ty,
                // punto de la foto que queda bajo los dedos (relativo al centro)
                ux: (p.x - box.cx - this.tx) / this.scale,
                uy: (p.y - box.cy - this.ty) / this.scale,
                moved: false,
            };
        } else if (this.pointers.size === 1) {
            const p = [...this.pointers.values()][0];
            this.gesture = { type: "pan", x0: p.x, y0: p.y, tx0: this.tx, ty0: this.ty, moved: false };
        }
    }

    onDown(ev) {
        if (ev.pointerType === "mouse" && ev.button !== 0) {
            return;
        }
        this.pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY, startX: ev.clientX, startY: ev.clientY, t: performance.now(), target: ev.target });
        if (this.pointers.size === 2) {
            try {
                this.container.setPointerCapture(ev.pointerId);
            } catch {
                // sin captura: el gesto igual sigue
            }
        }
        this.startGesture();
    }

    onMove(ev) {
        const p = this.pointers.get(ev.pointerId);
        if (!p || !this.gesture) {
            return;
        }
        p.x = ev.clientX;
        p.y = ev.clientY;
        const box = this.box;
        const g = this.gesture;
        if (g.type === "pinch" && this.pointers.size >= 2) {
            const now = this.pair();
            const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, (g.s0 * now.d) / g.d0));
            this.scale = s;
            this.tx = now.x - box.cx - s * g.ux;
            this.ty = now.y - box.cy - s * g.uy;
            g.moved = true;
            this.clamp();
            this.apply();
            ev.preventDefault();
        } else if (g.type === "pan") {
            const dx = p.x - g.x0;
            const dy = p.y - g.y0;
            if (Math.hypot(dx, dy) > 6) {
                g.moved = true;
            }
            const canPan = this.scale > 1.01 && !this.isVideo();
            if (canPan) {
                this.tx = g.tx0 + dx;
                this.ty = g.ty0 + dy;
                this.clamp();
                this.apply();
                ev.preventDefault();
            }
        }
    }

    onUp(ev) {
        const p = this.pointers.get(ev.pointerId);
        if (!p) {
            return;
        }
        const g = this.gesture;
        const dx = ev.clientX - p.startX;
        const dy = ev.clientY - p.startY;
        const wasPinch = g?.type === "pinch";
        this.pointers.delete(ev.pointerId);
        if (wasPinch) {
            this.blockClickUntil = performance.now() + TAP_MS;
            if (this.scale < 1.05) {
                this.reset(true);
            }
        } else if (g) {
            const dist = Math.hypot(dx, dy);
            if (g.moved && dist > TAP_PX) {
                this.blockClickUntil = performance.now() + 250;
                // deslizar a los lados sin zoom = foto siguiente/anterior (solo fotos)
                if (
                    this.onSwipe &&
                    this.scale <= 1.01 &&
                    !this.isVideo() &&
                    Math.abs(dx) > 60 &&
                    Math.abs(dx) > Math.abs(dy) * 1.5
                ) {
                    this.onSwipe(dx < 0 ? 1 : -1);
                }
            } else if (ev.type === "pointerup") {
                this.onTap(ev, p);
            }
        }
        this.gesture = null;
        if (this.pointers.size) {
            this.startGesture(); // quedó un dedo: sigue como arrastre
        }
    }

    // doble toque / doble clic sobre la foto
    onTap(ev, p) {
        const content = this.getContent();
        if (!content || this.isVideo() || !(p.target === content || content.contains(p.target))) {
            this.lastTap = null;
            return;
        }
        const now = performance.now();
        const prev = this.lastTap;
        if (prev && now - prev.t < TAP_MS && Math.hypot(ev.clientX - prev.x, ev.clientY - prev.y) < TAP_PX * 2) {
            this.lastTap = null;
            this.blockClickUntil = now + TAP_MS;
            if (this.scale > 1.05) {
                this.zoomTo(1, ev.clientX, ev.clientY);
            } else {
                this.zoomTo(DOUBLE_TAP_SCALE, ev.clientX, ev.clientY);
            }
        } else {
            this.lastTap = { t: now, x: ev.clientX, y: ev.clientY };
        }
    }

    onWheel(ev) {
        if (!this.getContent()) {
            return;
        }
        ev.preventDefault();
        const factor = Math.exp(-ev.deltaY * 0.0022);
        this.zoomTo(this.scale * factor, ev.clientX, ev.clientY, false);
    }

    // Después de pellizcar o arrastrar, el "clic" que el navegador dispara no debe cerrar ni abrir nada.
    onClick(ev) {
        if (performance.now() < this.blockClickUntil) {
            ev.stopPropagation();
            ev.preventDefault();
        }
    }
}
