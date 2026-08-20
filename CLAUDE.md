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
1. **Nunca hacer `git commit`/`git push` sin autorización explícita** en ese momento —
   una aprobación anterior no cubre el siguiente cambio.
2. Flujo por cada cambio, en este orden exacto:
   1. Editar el código localmente (con el visto bueno de qué cambiar).
   2. Generar un `.sh` de despliegue.
   3. Dar los comandos en orden: copiar módulo → verificar permisos → actualizar módulo → reiniciar Odoo.
   4. Andrés prueba en producción.
   5. Solo si confirma que funciona → recién ahí pedir permiso para commit + push.
3. Claude actúa como **coach**: explica el porqué de cada cambio, pero el criterio de
   negocio final es de Andrés (no es programador de formación).
4. Mantener este archivo **conciso** — no volcar contexto detallado de cada sesión aquí.
   Detalle largo va en memoria del harness (`memory/`), no en CLAUDE.md.

## Errores conocidos SIN resolver
_(actualizar esta lista cuando aparezca uno nuevo o se resuelva)_
- Ninguno registrado todavía.

## Historial de cambios (resumen, no detalle)
- 2026-08-20: Repo inicializado, primer commit hecho y subido a
  https://github.com/andresabg09/stock_picking_sale_buttons (público, remote `origin`,
  rama `master`).
