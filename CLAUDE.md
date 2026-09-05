# stock_picking_sale_buttons — Módulo Odoo 18

Módulo custom para **Chalón Panamá**. Botones inteligentes, ajustes visuales e imágenes
redimensionadas en Traslados (`stock.picking`), Ventas (`sale.order`), Facturas
(`account.move`), Productos y Compras (`purchase.order`), más reportes inheritados
(delivery slip, invoice, sale order).

## Infraestructura
- Odoo 18 self-hosted en una VM de **Google Cloud**, gestionada con **EasyPanel**.
- El dueño (Andrés) tiene horarios de bajo tráfico para actualizar/reiniciar en producción.
- No hay ambiente de staging — los cambios se prueban directo en producción, con cuidado.

## Reglas de trabajo (fijas, no reinterpretar)
1. Flujo por cada cambio, en este orden exacto:
   1. Editar el código localmente (con el visto bueno de qué cambiar).
   2. Claude hace commit + push **automáticamente, sin preguntar antes**, y avisa
      después con un mensaje corto.
   3. Dar el comando corto de despliegue: `sudo bash .../scripts/deploy.sh` (git pull).
   4. Andrés prueba en producción.
   REGLA DEFINITIVA (2026-08-20, confirmada explícitamente por Andrés tras varias
   idas y vueltas — no volver a cambiar sin que él lo pida de nuevo).
3. Claude actúa como **coach**: explica el porqué de cada cambio, pero el criterio de
   negocio final es de Andrés (no es programador de formación).
4. Mantener este archivo **conciso** — no volcar contexto detallado de cada sesión aquí.
   Detalle largo va en memoria del harness (`memory/`), no en CLAUDE.md.
5. **Sin acceso directo al servidor/código original de Odoo**: este módulo hereda/mejora
   módulos base (stock, sale, account, purchase, product). Cuando falte un dato del lado
   de Odoo (campo exacto, `xml id` de vista/reporte, ruta de módulo, estructura de modelo),
   pedirle a Andrés el comando SSH exacto a correr y esperar que pegue la salida antes de
   escribir el cambio. No asumir nombres sin confirmar.

## Infraestructura del servidor (Docker Swarm vía EasyPanel)
- Servicio Odoo: `crm_odoo` · BD: `shalom` · Carpeta módulo en el host (VM, bind mount):
  `/root/odoo-addons/stock_picking_sale_buttons`.
- Scripts listos en `scripts/`: `recon.sh` (recolectar estos datos si cambian),
  `setup_server_git.sh` (una sola vez: conectar la carpeta del servidor a este repo git),
  `deploy.sh` (rutina: pull → permisos → actualizar módulo → reiniciar servicio).

## Errores conocidos SIN resolver
_(actualizar esta lista cuando aparezca uno nuevo o se resuelva)_
- Menores/no bloqueantes (vistos en logs de actualización, no introducidos por este
  módulo): campos duplicados con etiqueta "Código de Barras" (Studio `x_codigo_barras`/
  `x_barcode` vs `custom_product_barcode`); `<img>`/`<i>` sin `alt`/`title` en vistas de
  facturas/ventas/compras del módulo.
- `ir.cron` en esta instalación (Odoo 18.0-20260513): NO tiene el campo `numbercall`
  (tumbó producción dos veces al intentar crear un cron con `numbercall` y luego con
  un `eval` de `nextcall` mal escrito). Antes de volver a crear un registro `ir.cron`,
  confirmar por SSH los campos exactos con
  `odoo shell -d shalom --no-http -c "print(env['ir.cron']._fields.keys())"`.

## Historial de cambios (resumen, no detalle)
- 2026-08-20: Repo inicializado, primer commit hecho y subido a
  https://github.com/andresabg09/stock_picking_sale_buttons (público, remote `origin`,
  rama `master`).
- 2026-08-20: Fix vencimiento Kanban vs Lista en traslados — Kanban ahora usa
  `scheduled_date` + `widget=remaining_days` (igual que la Lista). Desplegado y
  verificado en producción.
- 2026-08-20: Fix Kanban de facturas repetía nombre del producto en la descripción —
  nuevo campo compute `custom_extra_description` en `account.move.line` (quita la
  línea del nombre de producto de `name`, deja solo la nota del vendedor). Verificado.
- 2026-09-05: Exportación a Dianke (Excel) de órdenes de venta confirmadas — campo
  `custom_payment_method` en sale.order, botón "Enviar a Dianke ahora" dentro de cada
  orden confirmada, y acción masiva "Enviar a Dianke (Excel)" desde el listado de
  Ventas (selecciona varias y las manda juntas). Antes de enviar se abre un wizard de
  confirmación (`sale.dianke.email.wizard`) donde se puede editar destinatario, CC,
  asunto y cuerpo. El envío automático de las 11:59pm quedó **fuera por ahora**
  (pedido explícito de Andrés) — no hay registro `ir.cron` todavía (ver Errores
  conocidos: campos de `ir.cron` sin confirmar en esta versión). Pendiente de probar
  en producción.
