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
import { reactive, useState } from "@odoo/owl";
import { ProductCatalogKanbanRecord } from "@product/product_catalog/kanban_record";
import { ProductCatalogOrderLine } from "@product/product_catalog/order_line/order_line";

// Estado compartido por todas las tarjetas del catálogo abierto (se reinicia si cambia el pedido).
const promoStore = reactive({ orderId: null, loaded: false, byProduct: {} });

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
    async _updateQuantity() {
        await super._updateQuantity(...arguments);
        await this._dkRefreshPromo();
    },
    async _dkRefreshPromo() {
        // Solo Ventas; si algo falla, el catálogo sigue funcionando igual, sin la leyenda nueva.
        if (this.env.orderResModel !== "sale.order") {
            return;
        }
        try {
            const status = await rpc("/stock_picking_sale_buttons/catalog/promo_status", {
                order_id: this.env.orderId,
            });
            promoStore.orderId = this.env.orderId;
            promoStore.byProduct = status || {};
            promoStore.loaded = true;
        } catch (e) {
            console.warn("catalog_promo: no se pudo actualizar la leyenda de promoción", e);
        }
    },
});
