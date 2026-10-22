/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

/* Listas editables (líneas de la entrega, orden, compra...): tras cambiar la cantidad de una línea, esa fila
   sigue "en edición". Si después se da check ("Listo") en OTRAS filas, cada actualización de la pantalla hacía que
   Odoo volviera a enfocar la fila en edición y el navegador saltaba hasta ella (arriba o abajo). Ahora, si el
   cursor está en otra fila de la lista (un check, por ejemplo), no se le roba el foco. Al tocar la cantidad de
   cualquier fila todo funciona igual que siempre. */
patch(ListRenderer.prototype, {
    focusCell(column, forward = true) {
        const active = document.activeElement;
        const otherRow = active && active.closest && active.closest(".o_data_row");
        if (this.editedRecord && otherRow && !otherRow.classList.contains("o_selected_row")) {
            return;
        }
        return super.focusCell(column, forward);
    },
});
