/** @odoo-module **/

// Visor de adjuntos del log (el que se abre al tocar una foto o video adjunto): zoom como en una galería.
// Pellizcar con dos dedos, doble toque, arrastrar la foto acercada, rueda del mouse. También en videos (dos dedos).
// Reemplaza el zoom a saltos de Odoo (botones + / − y rueda), que no entiende los dedos. Ver dk_zoom.js.

import { onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { DkZoom } from "@stock_picking_sale_buttons/js/dk_zoom";

patch(FileViewer.prototype, {
    setup() {
        super.setup(...arguments);
        this.dkRoot = useRef("autofocus");
        this.dkZoom = null;
        onMounted(() => this.dkZoomInit());
        onPatched(() => this.dkZoomTouchAction());
        onWillUnmount(() => this.dkZoom?.detach());
    },

    get dkMain() {
        return this.dkRoot.el?.querySelector(".o-FileViewer-main");
    },

    dkZoomInit() {
        const main = this.dkMain;
        if (!main) {
            return;
        }
        this.dkZoom = new DkZoom({
            container: main,
            // la foto: se mueve su "zoomer" (el cuadro completo centrado); el video: el propio video
            getTarget: () => (this.state.file.isImage ? this.zoomerRef.el : main.querySelector("video")),
            getContent: () => (this.state.file.isImage ? this.imageRef.el : main.querySelector("video")),
            isVideo: () => Boolean(this.state.file.isVideo),
            onChange: (scale) => {
                this.state.scale = scale;
            },
        });
        this.dkZoom.attach();
        this.dkZoomTouchAction();
    },

    // Con foto o video los dedos son nuestros; con PDF o texto se dejan al navegador (para poder desplazarse).
    dkZoomTouchAction() {
        const main = this.dkMain;
        if (main) {
            main.style.touchAction = this.state.file.isImage || this.state.file.isVideo ? "none" : "";
        }
    },

    activateFile(index) {
        super.activateFile(...arguments);
        this.dkZoom?.reset();
    },

    // El zoom a saltos, la rueda y el arrastre de Odoo pasan a nuestro zoom.
    zoomIn() {
        this.dkZoom?.zoomBy(1.6);
    },

    zoomOut() {
        this.dkZoom?.zoomBy(1 / 1.6);
    },

    resetZoom() {
        this.dkZoom?.reset(true);
    },

    onWheelImage() {},
    onMousedownImage() {},
    onMouseupImage() {},
    onMousemoveView() {},
    updateZoomerStyle() {},

    // El tamaño y el giro siguen siendo de Odoo; el zoom ya no (lo hace el zoomer).
    get imageStyle() {
        let style = `transform: rotate(${this.state.angle}deg);`;
        if (this.state.angle % 180 !== 0) {
            style += `max-height: ${window.innerWidth}px; max-width: ${window.innerHeight}px;`;
        } else {
            style += "max-height: 100%; max-width: 100%;";
        }
        return style;
    },
});
