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
2. Para cambios de diseño/alcance no triviales (formato de un reporte, estructura de un
   Excel, flujo nuevo, etc.): primero **mostrar el diseño/plan y esperar la confirmación
   explícita de Andrés**, sin tocar código ni git. Recién cuando él confirma, se codifica
   y se aplica la regla 1 completa (commit + push automático, sin volver a preguntar en
   ese momento — la confirmación de diseño ya cubre el "ok" para programar y subir). No
   ir montando y subiendo cambios a cada rato mientras el diseño todavía se está afinando.
   REGLA DEFINITIVA (2026-09-05, pedida explícitamente por Andrés — no volver a cambiar
   sin que él lo pida de nuevo).
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
- 2026-09-05: Rediseño del Excel de Dianke tras feedback de Andrés — un solo archivo
  con 2 pestañas: "Importar" (plana, una fila por línea, para subida automática) y
  "Resumen" (un bloque por pedido: cabecera del cliente una sola vez + foto del local,
  tabla de productos debajo — sin repetir datos fijos). Contacto corregido: usa el
  campo de Studio `x_nombre_contacto` en res.partner (nombre de la persona, ej.
  "Julio"), separado de `name` (nombre del local). Pendiente de probar en producción.
- 2026-09-05: Ajustes al Excel de Dianke tras 2do feedback de Andrés — en "Importar"
  los campos fijos (cliente, RUC, teléfono, etc.) solo se llenan en la primera línea
  de cada pedido (en blanco en las siguientes del mismo pedido; ver Errores conocidos
  sobre el riesgo de que un importador espere valor en cada fila). En ambas pestañas,
  "Descripción/Notas" ya no repite el nombre del producto — solo muestra lo que sobra
  (ej. "CAMBIO X CAMBIO", "Producto gratis") vía `_dianke_extra_note`. "Resumen" ahora
  tiene formato de moneda y una fila de "Total del pedido" por bloque.
- 2026-09-05: Ajustes al Excel de Dianke tras 3er feedback de Andrés — "Importar" se
  redujo a solo 9 columnas (Orden de Venta, Contacto, Dirección, Código/Referencia,
  Producto, Descripción/Notas, Cantidad, Precio Unitario, Subtotal); todo lo demás
  (fecha, cliente, RUC, teléfono, celular, forma de pago) queda solo en "Resumen".
  Las filas con nota extra (cambio, gratis, etc.) se resaltan en rosa salmón pastel
  (`F8CBAD`) en "Importar".
- 2026-09-05: Ajustes al Excel de Dianke tras 4to feedback de Andrés — se agregó
  "Cliente" de vuelta en "Importar" (junto a Contacto) y "Código Anclado" en las 2
  pestañas (mismo `product.barcode.multi` que ya se usa en el Excel de compras a
  proveedores). Se corrigió la Dirección: antes usaba `contact_address_complete`
  (trae el nombre del cliente pegado al inicio); ahora se arma solo con
  street/street2/city/state/country del cliente, sin el nombre.
- 2026-09-05: REVERTIDO el punto de "campos fijos solo en la primera línea" del
  cambio anterior — Andrés aclaró que en "Importar" el sistema que la importe
  necesita poder identificar en CADA fila a qué cliente pertenece. Orden de Venta,
  Cliente, Contacto y Dirección vuelven a repetirse en todas las líneas del mismo
  pedido (diseño original). No volver a poner esto en blanco sin que lo pida de
  nuevo explícitamente.
- 2026-09-05: REDISEÑO COMPLETO del Excel de Dianke — Andrés compartió la plantilla
  oficial que Dianke usa para recibir pedidos ("Formato_para_recibir_pedidos_clientes.xlsx")
  y pidió usarla tal cual en vez de "Importar"/"Resumen". Ahora es 1 sola hoja
  ("Pedido Dianke"), con un bloque por orden en el formato/colores exactos de esa
  plantilla: Fecha, Nombre o razón social, RUC (agregado aunque no está en la
  plantilla original), Contacto, Dirección, Teléfono, Número de ruta, Número de
  pedido, Fecha de entrega, Tipo de pago (casillas), y debajo el detalle
  (Código/Descripción/Cantidad/Precio venta/Tipo de venta). Foto del local
  incrustada a un lado (fuera de las columnas A-E de la plantilla). Notas de
  detalles nuevos:
  - **Ruta**: se busca `fsm.location` con `partner_id = cliente` y se usa
    `fsm_route_id.name` (mapa de campos confirmado por Andrés).
  - **Fecha de entrega**: calculada (no hay campo que ya la calcule) — 4 días
    hábiles desde `date_order`, contando lunes a viernes, sin fines de semana,
    sin feriados.
  - **Tipo de pago**: Efectivo/Tarjeta se marcan directo; Transferencia se marca
    como ACH; Yappy/Crédito 1-2 semanas se agregan como una 4ta casilla
    "Otro: <forma de pago>" ya que la plantilla de Dianke no las contempla.
  - **Tipo de venta** (columna del detalle): "Normal" o la nota que escribió el
    vendedor (cambio, producto gratis, etc.) vía `_dianke_extra_note`; esas filas
    se resaltan en rosa salmón pastel (`F8CBAD`).
- 2026-09-05: Excel de Dianke: se agregaron los bordes finos y la fuente "Aptos"
  que trae la plantilla original de Dianke (antes solo se habían copiado los
  colores, no los bordes ni la fuente exacta).
- 2026-09-05: CERRADO el pendiente del correo a Dianke que se había quedado sin
  programar — CC fijo `andres@shalompma.com, luis@shalompma.com,
  milciades@shalompma.com` (constante `DIANKE_EMAIL_CC`); asunto dinámico
  singular/plural ("Pedido/Pedidos para Dianke Group — Orden/Órdenes de Venta
  ..."); cuerpo sin saludo por hora ("Querido equipo de Dianke,"), avisando que
  ahí está toda la información acordada y que identifiquen cualquier ajuste que
  necesiten, cerrando con la firma de Andrés Gutiérrez. Todo centralizado en
  `_dianke_subject_and_body()` para no duplicar el texto entre el envío directo
  y el wizard de confirmación.
- 2026-09-05: Excel de Dianke, 3 ajustes más — la foto del local ya no queda en
  una columna aparte desalineada: ahora es su propia fila "Foto del local"
  arriba de "Fecha", integrada al bloque (solo aparece si el cliente tiene
  foto). Se agregó "Código Anclado" de vuelta en el detalle (mismo
  `product.barcode.multi`). La Descripción y el "Tipo de venta" (cuando la nota
  es larga) ya no se cortan — `_dianke_estimate_row_height()` calcula la altura
  de cada fila según el texto más largo entre Código Anclado/Descripción/Tipo
  de venta (con `wrap_text`), en vez de una altura fija.
- 2026-09-05: Fix `_dianke_estimate_row_height` — la estimación de caracteres
  por línea (1.8 por unidad de ancho) se quedaba corta y varios nombres de
  producto largos se veían cortados al envolver en 2 líneas. Ajustado a 0.9
  caracteres por unidad de ancho (más conservador → detecta el wrap antes).
- 2026-09-05: REDISEÑO — el envío a Dianke ya no genera un solo Excel para
  todas las órdenes: ahora genera **un archivo por ruta** (`fsm_route_id.name`
  del cliente vía `fsm.location`), y dentro de cada archivo **una pestaña por
  cliente/pedido**, nombrada con el cliente, en el mismo orden en que se
  atienden en la ruta (`x_orden_ruta`, ascendente). Pedidos sin ruta asignada
  caen en un archivo aparte "Sin Ruta". Nombre de archivo: "Pedidos Dianke
  [Ruta] [Fecha].xlsx". El campo "Número de ruta" del bloque ahora muestra
  también la posición, ej. "Pedregal (Orden 15)". Todos los archivos van
  adjuntos en el mismo correo. Reemplaza `_generate_dianke_xlsx_bytes` +
  `_dianke_xlsx_filename` por `_generate_dianke_xlsx_files` (devuelve lista de
  archivos) + `_dianke_group_by_route` + `_dianke_safe_sheet_name`.
- 2026-09-05: Correo a Dianke — se agregó de forma PERMANENTE (parte del
  template, `_dianke_subject_and_body`) el bloque de "especificaciones de
  despacho" (Productos NNP Aliset 69gr/Decolorantes en unidades individuales,
  AER POCKETS por displays). La info sobre tintes en múltiplos de 5 (excepto
  Tinte N.º 1, reservado para cambios/promos/rotaciones) NO se agregó al
  código — Andrés pidió esa parte solo como texto suelto para copiar/pegar
  cuando la necesite, no como default de todos los correos.
- 2026-09-05: FIX IMPORTANTE — los correos SÍ se estaban mandando bien (el "no
  envía" reportado por Andrés era en realidad el navegador bloqueando la
  descarga de los adjuntos, "no se puede descargar de forma segura", por
  archivos de varios MB). Causa real: `_dianke_embed_partner_photo` solo
  cambiaba el tamaño VISUAL de la foto (`xl_img.width/height`), pero el
  binario incrustado seguía siendo la imagen original de Odoo (cientos de
  KB a varios MB) — con una foto por cliente y varios clientes por archivo
  de ruta, el Excel pesaba varios MB. Ahora se comprime de verdad con
  Pillow (thumbnail + JPEG calidad 70) antes de incrustarla. Probado: un
  archivo con 5 clientes/5 fotos pasó de pesar varios MB a ~18 KB.
- 2026-09-05: Asunto del correo a Dianke — ya no lista los números de orden
  (quedaba kilométrico con muchas órdenes). Ahora muestra las rutas con la
  cantidad de órdenes de cada una (ej. "Pedregal (5), Villa Grecia (3)") más
  la fecha del envío en español (ej. "Sábado 5 de Septiembre de 2026", vía
  nuevo `_dianke_fecha_larga_es`, escrita a mano sin depender del locale del
  servidor) — para distinguir de un vistazo si un envío es de hoy o de otro
  día (ej. si una ruta se manda en 2 partes en días distintos).
  `_dianke_subject_and_body` dejó de ser `@staticmethod` (ahora usa
  `self._dianke_route_info` para agrupar por ruta).
- 2026-09-05: FIX IMPORTANTE — el orden de las pestañas por ruta salía mal.
  Causa: `x_orden_ruta` es un Integer de Odoo — sin asignar, su valor por
  defecto es **0**, no None/vacío. `_dianke_group_by_route` solo trataba
  `None` como "sin asignar", así que todos los clientes con 0 (la mayoría,
  en la práctica) se ordenaban de PRIMEROS en vez de al final, antes que los
  que sí tenían una posición real (1, 2, 3...). Ahora 0 y None se tratan
  igual (sin asignar → al final del archivo de esa ruta). También se quitó
  el "(Orden 0)" engañoso que podía aparecer en el campo "Número de ruta"
  del bloque — confirmado con Andrés: 0/vacío en `x_orden_ruta` = sin orden
  asignado, no una posición real.
- 2026-09-05: Se agregó `kenniarueda@diankegroup.com` al correo principal
  (`DIANKE_EMAIL_TO`).
- 2026-09-05: Conversión display→unidades para las 6 referencias AMB GODREJ
  POCKET (Berry Rush, Bright, Fresh Blossom, Sea Breeze, Floral Delight,
  etc.) en el Excel de Dianke — Andrés las maneja por display (1 display = 6
  unidades) pero Dianke las necesita en unidades. `_dianke_is_godrej_pocket`
  detecta el producto por nombre (requiere "GODREJ" y "POCKET" en el
  nombre, sin importar el orden de las palabras, porque varía entre
  referencias). Cuando aplica: Cantidad ×6, Precio venta ÷6 (así el
  subtotal cantidad×precio sigue representando el mismo valor real del
  pedido, solo que en unidades en vez de displays) — confirmado con Andrés.
- 2026-09-05: "Precio venta" del Excel de Dianke siempre a 2 decimales —
  se notaba sobre todo con la conversión de GODREJ POCKET (4.25÷6 =
  0.7083333...). Se redondea el valor (`round(precio, 2)`) y además se le
  pone `number_format = '0.00'` a la celda, para que Excel siempre lo
  muestre en 2 decimales sin importar el cálculo. El Excel de compras a
  proveedores no tiene columna de precio, así que no le aplica esto.
