/** @odoo-module **/

// Catálogo de productos de Ventas: leyenda de promoción en vivo.
//
// Muestra en cada tarjeta la MISMA leyenda que la columna "Promo" de la cotización
// (sale.order.line.custom_promo_status: "✅ Tienes 2 promos completas…" / "⏳ Faltan 4 unidades…"),
// y la actualiza después de cada cambio de cantidad, sin salir del catálogo.
// La primera carga viene del servidor (`promoStatus`, ver models/sale_order_catalog.py); después de cada
// cambio se piden de nuevo todas las leyendas (una promo suma varios productos, y al cambiar uno
// pueden cambiar los demás).

import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { onPatched, onWillPatch, reactive, useState } from "@odoo/owl";
import { ProductCatalogKanbanRecord } from "@product/product_catalog/kanban_record";
import { ProductCatalogOrderLine } from "@product/product_catalog/order_line/order_line";

// Estado compartido por todas las tarjetas del catálogo abierto (se reinicia si cambia el pedido).
const promoStore = reactive({ orderId: null, loaded: false, byProduct: {}, ticket: 0 });

// Propiedad nueva que llega desde el servidor.
ProductCatalogOrderLine.props = {
    ...ProductCatalogOrderLine.props,
    promoStatus: { type: String, optional: true },
};

patch(ProductCatalogOrderLine.prototype, {
    setup() {
        super.setup(...arguments);
        // Primero se reinicia el estado si es otro pedido, y recién después se suscribe el componente
        // (así no se dispara un redibujado de un componente que todavía no está montado).
        if (this.env.orderId !== promoStore.orderId) {
            promoStore.orderId = this.env.orderId;
            promoStore.loaded = false;
            promoStore.byProduct = {};
        }
        this.dkPromo = useState(promoStore);
        // Cuando Odoo vuelve a dibujar la tarjeta (llegó el precio del servidor o la leyenda de promoción) la caja
        // de cantidad se reponía al valor guardado y se perdía lo que el usuario estaba escribiendo ("Agregar" → escribir
        // 12 → volvía a 1). Si la caja tiene el foco, se recuerda lo escrito antes de dibujar y se devuelve después.
        let typing = null;
        onWillPatch(() => {
            const el = document.activeElement;
            typing =
                el && el.tagName === "INPUT" && el.closest(".o_product_catalog_quantity")
                    ? { el, value: el.value }
                    : null;
        });
        onPatched(() => {
            if (typing && typing.el.isConnected && typing.el.value !== typing.value) {
                typing.el.value = typing.value;
            }
            typing = null;
        });
    },
    get promoText() {
        if (this.dkPromo.loaded) {
            return this.dkPromo.byProduct[this.props.productId] || "";
        }
        return this.props.promoStatus || "";
    },
    get promoClass() {
        return (this.promoText || "").startsWith("✅") ? "is-ok" : "is-wait";
    },
});

patch(ProductCatalogKanbanRecord.prototype, {
    // Los cambios de cantidad de una misma tarjeta salen UNO POR UNO, en orden. La versión de Odoo de este
    // servidor los manda en paralelo: "Agregar" (cantidad 1) todavía se estaba guardando cuando salía el "12",
    // y el servidor terminaba con el 1 (la cantidad "se reponía"). Cada envío lee la cantidad al momento de
    // salir, así que siempre lleva lo último que escribió el usuario.
    _updateQuantityAndGetPrice() {
        const send = () =>
            rpc("/product/catalog/update_order_line_info", this._getUpdateQuantityAndGetPriceParams());
        const previous = this._dkPendingUpdate || Promise.resolve();
        this._dkPendingUpdate = previous.then(send, send);
        return this._dkPendingUpdate;
    },
    async _updateQuantity() {
        await super._updateQuantity(...arguments);
        await this._dkRefreshPromo();
    },
    async _dkRefreshPromo() {
        // Solo Ventas; si algo falla, el catálogo sigue funcionando igual, sin la leyenda nueva.
        if (this.env.orderResModel !== "sale.order") {
            return;
        }
        const ticket = (promoStore.ticket = (promoStore.ticket || 0) + 1);
        try {
            const status = await rpc("/stock_picking_sale_buttons/catalog/promo_status", {
                order_id: this.env.orderId,
            });
            if (ticket !== promoStore.ticket) {
                return; // llegó una respuesta más nueva: esta ya quedó vieja
            }
            promoStore.orderId = this.env.orderId;
            promoStore.byProduct = status || {};
            promoStore.loaded = true;
        } catch (e) {
            console.warn("catalog_promo: no se pudo actualizar la leyenda de promoción", e);
        }
    },
});
