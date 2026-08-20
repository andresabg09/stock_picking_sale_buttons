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
   2. Dar los comandos de despliegue (`scripts/deploy.sh`, requiere `sudo`).
   3. Andrés prueba en producción.
   4. Solo si confirma que funciona → Claude hace commit + push **automáticamente, sin
      preguntar antes**, y avisa después que ya quedó en GitHub. Nunca push de algo no
      confirmado como funcionando (regla actualizada 2026-08-20).
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
- Ninguno registrado todavía.

## Historial de cambios (resumen, no detalle)
- 2026-08-20: Repo inicializado, primer commit hecho y subido a
  https://github.com/andresabg09/stock_picking_sale_buttons (público, remote `origin`,
  rama `master`).
