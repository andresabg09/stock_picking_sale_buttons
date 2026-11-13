/** @odoo-module **/
import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

/* Aviso de promoción de cada línea de la orden de entrega. El texto no viene de la línea sino de UN campo del
   traslado (`custom_promo_json` = {id_de_línea: texto}); así, al marcar varios "Listo" rápido, ninguna respuesta
   atrasada del servidor toca las filas (ver models/stock_picking.py). Se redibuja solo cuando cambia ese campo. */
export class DkPromoNote extends Component {
    static template = xml`<span class="dk-promo-note" t-esc="text"/>`;
    static props = ["*"];

    get text() {
        const record = this.props.record;
        const root = record.model.root;
        let notes = {};
        try {
            notes = JSON.parse(root.data.custom_promo_json || "{}") || {};
        } catch (e) {
            notes = {};
        }
        return (record.resId && notes[record.resId]) || "";
    }
}

registry.category("fields").add("dk_promo_note", {
    component: DkPromoNote,
    supportedTypes: ["char"],
});
