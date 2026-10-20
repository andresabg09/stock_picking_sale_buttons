/** @odoo-module **/
// Botón "Por agotar" del panel de Compras: abre la pantalla Compras > Por agotar.
// La plantilla vive en static/src/xml/purchase_por_agotar.xml.
import { patch } from "@web/core/utils/patch";
import { PurchaseDashBoard } from "@purchase/views/purchase_dashboard";

patch(PurchaseDashBoard.prototype, {
    openPorAgotar() {
        this.action.doAction("stock_picking_sale_buttons.action_dk_por_agotar");
    },
});
