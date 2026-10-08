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
   EXCEPCIÓN pedida por Andrés (2026-10-07) SOLO para el rediseño "Versión H": se trabaja
   en lotes de 3 etapas y se hace UN commit + push por lote (no por cambio). El plan está
   en el doc "Plan de rediseño H para Odoo" (claude.ai/code/artifact/4a80a50e-eafc-4ccc-a061-2fbf89f055d4).
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
5. **Sin acceso al código fuente/servidor de Odoo, pero SÍ consulta de datos vía MCP**:
   este módulo hereda/mejora módulos base (stock, sale, account, purchase, product).
   Cuando falte un dato del lado de Odoo (campo exacto, estructura de modelo, datos de
   prueba, `xml id` de vistas/reportes), **consultarlo primero por el conector MCP de
   Odoo** (ver sección "Acceso a Odoo por MCP") — ya no pedirle a Andrés el comando SSH
   para eso. Pedir SSH solo para lo que el MCP no alcanza: código fuente de módulos base
   en disco, logs, `odoo shell`, y el despliegue. No asumir nombres sin confirmar.
6. **Escrituras en Odoo por MCP** (`odoo_create`, `odoo_write`, `odoo_call_method`):
   cambian la BD de producción y disparan automatizaciones. Nunca sin decirle a Andrés
   qué se va a hacer y esperar su confirmación explícita, caso por caso.

## Infraestructura del servidor (Docker Swarm vía EasyPanel)
- Servicio Odoo: `crm_odoo` · BD: `shalom` · Carpeta módulo en el host (VM, bind mount):
  `/root/odoo-addons/stock_picking_sale_buttons`.
- Scripts listos en `scripts/`: `recon.sh` (recolectar estos datos si cambian),
  `setup_server_git.sh` (una sola vez: conectar la carpeta del servidor a este repo git),
  `deploy.sh` (rutina: pull → permisos → actualizar módulo → reiniciar servicio).

## Acceso a Odoo por MCP (AnythingMCP)
- Conector **"Odoo JSON-RPC"** en AnythingMCP (cloud.anythingmcp.com, cuenta de Andrés),
  hacia el Odoo de producción (BD `shalom`), con el usuario `ventas@shalompma.com`
  (uid 2). Hereda los permisos de ese usuario. Probado y funcionando (2026-10-04).
- Herramientas de **lectura** (usar libremente): `odoo_search_read`, `odoo_read`,
  `odoo_search_count`, `odoo_fields_get`, `odoo_list_*`. Siempre pasar `fields`.
- Herramientas de **escritura**: ver regla 6 (confirmación explícita antes de cada una).
- Credenciales: la clave API vive solo en AnythingMCP → conector → Environment Variables
  (`ODOO_API_KEY`, junto a `ODOO_URL`, `ODOO_DB`, `ODOO_UID`). **Nunca pegarla en el
  chat ni en el repo**; si se filtra, borrarla en Odoo (Preferencias → Seguridad de la
  cuenta) y crear otra. `MOTIS_URL` en esas variables es un sobrante, ignorar.
- Si da `Access Denied`: clave/uid/BD no coinciden (clave, usuario y base deben ser del
  mismo usuario) o falta `ODOO_API_KEY` en las variables.
- Límites: el MCP lee/escribe **datos**, no el código. Cambios al módulo siguen el flujo
  de la regla 1 (commit + push → `deploy.sh` por SSH). Logs y `odoo shell` siguen por SSH.

## Errores conocidos SIN resolver
_(actualizar esta lista cuando aparezca uno nuevo o se resuelva)_
- Menores/no bloqueantes (vistos en logs de actualización, no introducidos por este
  módulo): campos duplicados con etiqueta "Código de Barras" (Studio `x_codigo_barras`/
  `x_barcode` vs `custom_product_barcode`); `<img>`/`<i>` sin `alt`/`title` en vistas de
  facturas/ventas/compras del módulo.
- `ir.cron` en esta instalación (Odoo 18.0-20260513): NO tiene el campo `numbercall`
  (tumbó producción dos veces al intentar crear un cron con `numbercall` y luego con
  un `eval` de `nextcall` mal escrito). Antes de volver a crear un registro `ir.cron`,
  confirmar por SSH los campos exactos (ver comando correcto de `odoo shell` abajo).
- `odoo shell` (dentro del contenedor `crm_odoo`) NO tiene una bandera `-c` para código
  en línea como `python -c` — `-c`/`--config` ahí es el archivo de configuración, y usarlo
  para pasar código da el error "config file ... doesn't exist". Para correr código hay
  que pasarlo por stdin (heredoc). Además el nombre real del contenedor en Docker Swarm
  lleva un sufijo (ej. `crm_odoo.1.vv46yklchkzgsa109o8hbuwn0`), no es solo `crm_odoo` — hay
  que resolverlo primero. Y el `odoo.conf` de adentro del contenedor NO trae host/usuario/
  clave de la base (los pone EasyPanel como variables de entorno `HOST`/`PORT`/`USER`/
  `PASSWORD`, no en el archivo) — sin pasarlas explícitas da
  `psycopg2.OperationalError: ... /var/run/postgresql/.s.PGSQL.5432 ... No such file`.
  Patrón correcto completo (mismo que ya usa `deploy.sh` para actualizar el módulo):
  ```bash
  CID=$(docker ps --filter "name=crm_odoo." --format "{{.Names}}" | head -n1)
  DB_HOST=$(docker exec "$CID" printenv HOST)
  DB_PORT=$(docker exec "$CID" printenv PORT)
  DB_USER=$(docker exec "$CID" printenv USER)
  DB_PASS=$(docker exec "$CID" printenv PASSWORD)
  docker exec -i "$CID" odoo shell -d shalom --no-http \
    --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASS" <<'PYEOF'
  print(env['ir.cron']._fields.keys())
  PYEOF
  ```

## Historial de cambios (resumen, no detalle)
- 2026-10-04: Rediseño de la tienda web (nombre comercial por ahora **SHALOM PANAMÁ**, paleta
  blanco/azul oscuro `#0B1F3A`/negro), hecho por MCP. Fase 1+2 EN VIVO: `ir.ui.view` 3328 +
  `website.page` 11 (`/inicio`) = nuevo inicio, `website.homepage_url='/inicio'`; vistas
  activas 3329 (tema CSS que pisa la paleta oscura del sitio + barra superior) y 3330 (pie),
  heredan de `website.layout` (1013); menú 7 renombrado "Catálogo"; `website.name` =
  SHALOM PANAMÁ. Inicio viejo (`/shalom`, pages 8 y 9, view 2890) despublicado, NO borrado.
  Revertir: desactivar 3329 y 3330, `homepage_url='/shalom'`, republicar pages 8 y 9, menú 7
  → "Inicio", `website.name`='My Website'. La paleta oscura (negro, texto blanco) vive en
  los ir.attachment 36083/27478 (`user_color_palette.scss`/`user_values.scss`).
  2026-10-04 (tarde): CAUSA REAL del fondo negro/texto blanco en catálogo, ficha, carrito y
  login: el campo `website.custom_code_head` (id 1) traía un tema oscuro completo (3 `<style>`
  con `#09090B !important`, tarjetas con brillo azul, animaciones `.animate-on-scroll`, AOS de
  unpkg). Se REEMPLAZÓ por un comentario; copia exacta en
  `scripts/tienda_backup/ORIGINAL_website_custom_code_head.html` (revertir = escribir ese
  contenido en `custom_code_head`). También se reescribió la paleta (ir.attachment
  36083/27478 → paleta clara; sí se aplicó, el bundle CSS cambió de hash; originales en
  `scripts/tienda_backup/ORIGINAL_*.scss`) y se agregó a la vista 3329 un bloque CSS "Lectura
  clara" (fondo claro + texto negro en `main`, salvo `#dk-home`, botones y `.o_cc3/.o_cc5`).
  Verificado con navegador real contra la tienda (390 y 1280 px): 0 textos con bajo contraste.
  El form de login nace `d-none` y Odoo lo muestra por JS (en pruebas tarda ~8 s, es normal).
  Fase 3 pendiente = buscador tolerante a errores/abreviaturas + pedido rápido
  (requiere código aquí + deploy).
  2026-10-05: Buscador en el encabezado + inicio estilo banners (pedido de Andrés, ref.
  carbonestore.com), hecho por MCP: vista nueva `ir.ui.view` 3331 (`website.dianke_header_search`,
  hereda 1056 `placeholder_header_brand`) = barra "Buscar productos…" junto al logo (GET /shop);
  la lupa vieja, el teléfono y el botón CTA del header se ocultan por CSS en la vista 3329
  (que además lleva la barra superior con teléfono/WhatsApp). Vista 3328 (`/inicio`) ahora abre
  con banner "Nuevos productos" + 2 promos, carrusel Promociones (de `loyalty.program`
  buy_x_get_y activos), carrusel Nuevos productos (12), categorías con foto y marcas.
  Revertir buscador: desactivar 3331. Revertir inicio: restaurar
  `scripts/tienda_backup/PREVIOUS_inicio_view3328_con_buscador_arriba.xml` en la vista 3328.
  Ojo: el buscador del header sigue siendo el estándar de Odoo (la tolerancia es Fase 3).
  2026-10-05 (después): Por pedido de Andrés se QUITARON las promociones visibles del inicio
  (banners laterales + sección "Promociones"; ya no se lee `loyalty.program` ahí). El banner
  ahora es un carrusel de 5 slides (Nuevos productos, Shampús, Tintes NNP, Tratamientos,
  Corporales; fotos reales por categoría) que avanza solo cada 5 s, con flechas (escritorio),
  puntos, deslizable con el dedo; se pausa al pasar el mouse/tocar y respeta
  `prefers-reduced-motion`. JS inline al final de la vista 3328. Revertir: restaurar
  `scripts/tienda_backup/PREVIOUS_inicio_view3328_con_promociones.xml` en la vista 3328.
- 2026-10-05: Fase 3 de la tienda (código en el módulo, versión 18.0.2.1.0, nueva dependencia
  `website_sale`) — buscador tolerante + Pedido rápido. Verificado por SSH el código real de
  Odoo (regla 5): `website._search_with_fuzzy` → `_search_exact` → `product.template._search_fetch`;
  `_search_build_domain` acepta `search_extra(env, término)` por palabra (se suma con OR).
  Piezas: modelo `shop.search.synonym` (sinónimos editables: Ventas → Configuración →
  "Sinónimos de búsqueda (tienda)", datos iniciales `noupdate`: SHP/TRAT/ACD/PRF/AMB/DEO/COS/
  EST/BELL); campo almacenado `product.template.search_index` (nombre sin tildes, nombre pegado
  "xcare", categorías, código de barras principal + `barcode_ids`); override de
  `_search_get_detail` (agrega `search_extra`, NO toca `search_fields` para no ensuciar el
  corrector) y de `website._search_with_fuzzy` (busca primero lo escrito con sinónimos y solo si
  no hay nada deja actuar al corrector de Odoo). Página `/pedido-rapido` (solo con sesión;
  `controllers/quick_order.py`): interpreta líneas "código x cantidad" / "nombre cantidad",
  muestra qué entendió y agrega al carrito con la misma llamada que `/shop/cart/update`.
  Ningún producto tiene `default_code`; los códigos útiles son `barcode` y `barcode_ids`.
  Pendiente tras el deploy: autocompletado en el buscador del encabezado (vista 3331, usar el
  formulario nativo `website.website_search_box_input`), enlace "Pedido rápido" en el menú
  (`website.menu`), probar "Agregar" del inicio (nunca se probó de punta a punta).
  Rediseño de la tienda (diseño APROBADO por Andrés el 2026-10-05, maqueta en el artifact
  "Tienda — Propuesta estilo tienda"): estilo tienda tipo Amazon, NO catálogo de venta en
  calle (la sección se llama "Tienda", nunca "Catálogo"). Regla de negocio: al escribir una
  cantidad en cualquier producto ya queda en el carrito (sin botón de confirmar; la cotización
  en Ventas la crea Odoo). Sugerencias: otras fragancias del producto, misma marca, nuevos,
  comprados juntos. Por etapas, cada una con deploy: ETAPA 1 (hecha, v18.0.2.2.0) tarjetas
  con Agregar→cantidad viva (`/shop/dk/set_qty`, JS `shop_live_cart.js`, CSS
  `shop_live_cart.css`, vistas en `views/website_shop_templates.xml` montadas SOBRE
  `website_sale.products_item` sin reemplazarla), etiquetas Nuevo (`product.template.dk_is_new`,
  <30 días, parámetro `stock_picking_sale_buttons.new_days`) y Rebaja, píldora flotante del
  carrito. ETAPA 2 (hecha, v18.0.2.3.0) ficha de producto: caja de cantidad viva
  (`.dk-pbox`, atajos 12/24/48/96, "Ver carrito"/"Finalizar compra") montada ANTES de
  `#o_wsale_cta_wrapper` en `website_sale.product` (la caja nativa se oculta por CSS solo en
  productos de 1 variante; con variantes sigue la nativa), referencia/código de barras bajo el
  título, y secciones "De la misma línea" (`product._dk_siblings`: misma "línea" = palabras del
  nombre hasta la medida, vía `search_index`) y "Te puede interesar" (`_dk_suggestions`:
  comprados juntos en `sale.order.line` → misma categoría → nuevos). Tarjeta reutilizable
  `dk_card`. Pendientes: etapa 3 carrito, etapa 4 secciones Nuevos/Rebajas/Te puede interesar
  en tienda e inicio, mini carrito del encabezado, menú "Pedido rápido". "Rebaja" es solo precio tachado real
  (base_price > price_reduce); los precios de las maquetas con rebaja eran de ejemplo.
  Andrés autorizó (2026-10-05) subir a master automáticamente cada cambio (avance directo).
  LECCIÓN de contraste: el tema (vista 3329, bloque "Lectura clara") fuerza texto NEGRO con
  `!important` a todo lo que esté dentro de `main` y no sea `.btn`, `.badge`, `.fa`, `img`/`svg`,
  `.o_cc3/.o_cc5`. Cualquier botón/etiqueta nuevo con fondo oscuro DEBE llevar la clase `btn
  btn-primary` (o `badge`), o sus letras salen negras sobre azul (pasó con "Agregar" y las
  etiquetas Nuevo/Rebaja en la etapa 1; corregido). La píldora del carrito no muestra dinero
  (pedido de Andrés): solo "N productos" y "N unidades en tu carrito".
- 2026-10-05 (noche): REDISEÑO COMPLETO de tienda/ficha/carrito (v18.0.2.4.0) — Andrés dijo que
  las etapas 1-2 se veían "igual que antes"; ahora se REEMPLAZA el diseño nativo, como las maquetas.
  `views/website_shop_page.xml` (`dk_shop_page`, reemplaza `#wrap` de `website_sale.products`:
  barra lateral de categorías, Nuevos / Todos / Lo más pedido, paginado), y
  `views/website_shop_product_cart.xml` (ficha: migas propias + tarjeta Detalles; carrito: líneas
  en tarjetas con ganchos nativos `js_quantity`/`js_delete_product`/stock/loyalty + "Te puede
  interesar" vía `_dk_cart_suggestions`). Todas priority=99 (corren después de las nativas).
  CSS en `shop_redesign.css`. Revertir = desactivar `dk_shop_page`, `dk_product_page`,
  `dk_cart_lines`, `dk_cart_page` (Ajustes → Técnico → Vistas). La ficha oculta por CSS el texto
  en inglés de "garantía 30 días / envío 2-3 días" del tema. Pendiente: probar en producción.
- 2026-10-06: Buscador del encabezado — el autocompletado nativo (vista 3331 con `s_searchbar_input`)
  se trababa al borrar y no cargaba en tienda/ficha/carrito. Ahora las sugerencias son propias:
  `controllers/shop_suggest.py` (`/shop/dk/suggest`, mismo buscador tolerante) + `header_search.js`
  (frena los eventos del campo en captura para que el widget nativo no intervenga) + CSS en
  `shop_redesign.css` (v18.0.2.5.0). Hechos por MCP con confirmación de Andrés: menú 7 → "Tienda",
  menú nuevo "Pedido rápido" (id 9), pie (vista 3330) con "Tienda"/"Pedido rápido", parámetro
  `stock_picking_sale_buttons.new_days`=120 (id 65). Respaldos de 3330/3331 en `scripts/tienda_backup/`.
  "Nuevos en la tienda" no sale porque los productos recientes no tienen categoría web.
- 2026-10-06 (noche): Categorías por ventas + banner de servicio (v18.0.2.6.0). `product.public.category
  ._dk_top_categories(8, 90)` (models/product_public_category.py) = las 8 más vendidas (líneas de
  pedido confirmado, 90 días, sin precio 0), automático. Tienda: barra lateral "Más vendidas" + "Más
  categorías" plegable (chips del celular en el mismo orden). Inicio (vista 3328, escrita por MCP
  con permiso): categorías vía `t-call stock_picking_sale_buttons.dk_home_categories` y banner con 3
  mensajes de servicio (Pedido rápido / Despachos+WhatsApp / Repite tu pedido) en vez de repetir
  productos. Respaldo de la vista anterior: `scripts/tienda_backup/PREVIOUS_inicio_view3328_carrusel_productos.xml`;
  la nueva: `NEW_inicio_view3328_banner_servicio.xml`. Nombres de categoría corregidos por MCP (con
  permiso): ids 330 "Tratamientos", 331 "Wipes", 293 "Pies". OJO: el nombre es traducible y el sitio
  solo tiene `es_419` activo — hay que escribir con `context.lang=es_419` (odoo_call_method/write), si no
  solo cambia el idioma base y la tienda no lo muestra. Agrupar en familias queda para después.
- 2026-10-04: Conexión MCP a Odoo (conector "Odoo JSON-RPC" en AnythingMCP) — permite
  consultar campos, vistas y datos sin pasar por SSH (ver "Acceso a Odoo por MCP"). Causa
  del `Access Denied` inicial: faltaba la variable `ODOO_API_KEY` en Environment
  Variables (la clave que se pegaba en "Authentication" no es la que usa el conector).
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
- 2026-09-05: Correo a Dianke — se actualizó el bloque PERMANENTE de
  "especificaciones de despacho" (`_dianke_subject_and_body`): ya no dice
  "los AER POCKETS se despachan por displays" (quedó desactualizado desde
  que se empezó a convertir GODREJ POCKET a unidades) — ahora dice que los
  ambientadores Pocket también van en unidades, con la conversión ya
  ajustada.
- 2026-09-07: Visibilidad de envíos a Dianke en Ventas — pedido de Andrés:
  que cualquiera del equipo (no solo él) vea qué pedidos ya se mandaron a
  Dianke, cuándo y quién los mandó, sin que él tenga que avisar. Nuevo
  campo `custom_dianke_exported_by` (usuario) junto a los ya existentes
  `custom_dianke_exported`/`custom_dianke_exported_date`. Al confirmar el
  envío (wizard `sale.dianke.email.wizard`, botón individual o acción
  masiva "Enviar a Dianke (Excel)") queda un mensaje en el chatter de cada
  orden y un banner visible al abrir la orden. En la lista y el kanban de
  Ventas (Órdenes y Cotizaciones) se agregaron columnas/indicador de envío
  y resaltado (`decoration-warning`) para las confirmadas y aún no
  enviadas, más filtros "Pendientes de Dianke" / "Enviados a Dianke" y
  agrupar por estado de envío. Xml id de las vistas core de `sale.order`
  (lista, kanban, búsqueda — separadas para Órdenes y Cotizaciones)
  confirmados por SSH con Andrés antes de escribir los xpaths (regla 5).
  Los envíos hechos ANTES de este cambio no tienen mensaje en el chatter
  ni usuario registrado — solo los envíos nuevos quedan completos.
- 2026-09-08: Excel de Dianke, 2 filas nuevas en el bloque de cada pedido —
  pedido de Andrés (necesita que Dianke sepa a quién preguntarle por
  cambios/reemplazos, y dónde queda exactamente el cliente):
  "Vendedor" (después del nombre del negocio, usa el campo estándar
  `user_id` de `sale.order`) y "Ubicación GPS" (después de la dirección,
  link cliqueable a **Waze**, no Google Maps — confirmado con Andrés).
  El link se arma con `partner_latitude`/`partner_longitude` (estándar de
  Odoo en `res.partner`, mismo par que usa el botón "Ir con Waze" del
  módulo de rutas) vía nuevo `_dianke_waze_link`, formato
  `https://waze.com/ul?ll=<lat>,<lng>&navigate=yes`. Si el cliente no
  tiene coordenadas registradas, la celda muestra "Sin coordenadas
  registradas" en vez de un link roto.
- 2026-09-08: Forma de Pago obligatoria para confirmar una orden — pedido
  de Andrés. Nuevo campo `custom_special_delivery_date` ("Fecha especial
  de entrega", opcional, visible en el formulario junto a Forma de Pago).
  `action_confirm` de `sale.order` queda sobrescrito: si falta la Forma de
  Pago, en vez de confirmar abre el pop-up `sale.confirm.payment.wizard`
  (Forma de Pago obligatoria, precargada con la última usada por ESE
  cliente vía `_last_payment_method_for_partner` pero editable; Fecha
  especial de entrega opcional) — al confirmar el pop-up guarda ambos
  datos y recién ahí confirma la orden de verdad
  (`with_context(skip_payment_method_check=True)`, para no volver a caer
  en el mismo chequeo). Se enganchó en el método estándar de Odoo
  (`action_confirm`) para que cubra tanto el botón "Confirmar" de la
  cotización como el del módulo de rutas Shalom (otro módulo/repo, no
  probado desde aquí — pendiente que Andrés confirme en producción que
  también le sale el pop-up desde ahí). Si se confirman varias órdenes a
  la vez y a alguna le falta la Forma de Pago, no se abre el pop-up —
  sale un error pidiendo confirmarlas una por una. Se agregó "Cheque" a
  las opciones de Forma de Pago (cae en "Otro: Cheque" en el Excel de
  Dianke, que no tiene casilla propia para cheque). Si hay Fecha especial
  de entrega cargada, el Excel de Dianke la usa en vez de la calculada de
  3-4 días hábiles.
- 2026-09-08: Fix del pop-up de confirmar orden — `payment_method` en
  `sale.confirm.payment.wizard` tenía `required=True` a nivel de campo,
  así que Odoo fallaba al CREAR el wizard vacío (antes de que el usuario
  llegara a verlo) cuando no había ninguna orden anterior del cliente con
  forma de pago para precargar. La obligatoriedad ahora se valida al
  confirmar (ya existía ese chequeo) y en la vista (`required="1"`), no
  al crear el registro. Confirmado por Andrés que ya funciona en
  producción.
- 2026-09-08: Bug encontrado (no corregido acá, es otro repo) en
  `shalom_route_sales` — el botón "Confirmar pedido" de la app del
  vendedor (`fsm_order.py::shalom_confirmar_pedido`) llama al mismo
  `action_confirm()` de `sale.order`, pero ignora lo que devuelve y sigue
  cerrando la visita como "Completada" aunque la orden se quede sin
  confirmar por falta de Forma de Pago. Por pedido explícito de Andrés,
  **no se tocó ese repo** — se le entregó un prompt detallado para que lo
  arreglen aparte, agregando un pop-up nativo de Forma de Pago/Fecha
  especial/ITBMS dentro de la app (sin redirigir al navegador), que solo
  aplica al confirmar un pedido (no al revisar/guardar cotización).
- 2026-09-08: Opción "Incluye ITBMS" — pedido de Andrés: es solo
  informativa (NO toca ningún cálculo de impuestos de la orden), para que
  Dianke sepa si cobrarlo al entregar la mercancía (Dianke es quien
  entrega, no Chalón). Nuevo campo `custom_itbms_required` (Boolean,
  default True) en `sale.order`. Se agregó al mismo pop-up de confirmación
  (`sale.confirm.payment.wizard`), se elige en CADA pedido (no es fijo por
  cliente), precargado con la última elección de ESE cliente vía nuevo
  `_last_itbms_choice_for_partner` (mismo patrón que la Forma de Pago).
  En el Excel de Dianke se agregó como fila de casillas "Con ITBMS" /
  "Sin ITBMS" junto a "Tipo de pago".
- 2026-09-10: El botón nativo de Odoo para reclamar recompensa ("compra X
  y llévate Y") ahora respeta el mismo criterio de precio que ya usa la
  columna "Promo" — pedido de Andrés: una línea con precio muy rebajado
  no debe contar para desbloquear el regalo. Nuevo override de
  `_get_not_rewarded_order_lines()` (método nativo de `loyalty`/
  `sale_loyalty`, hoy solo saca las líneas de regalo ya aplicadas): además
  saca las líneas que no pasan `_price_qualifies_for_promo` para algún
  programa `buy_x_get_y` activo (mismas funciones que ya usa
  `_compute_custom_promo_status`, sin duplicar lógica). Solo afecta
  programas `buy_x_get_y` (los 8 activos hoy: pocket, Aliset, Big Puff
  300/750ml, peróxidos/decolorante Nevada, trat-skala, tintes) — no toca
  "Tarjetas de regalo" (`gift_card`), que no usa `rule_ids` con cantidad
  mínima. Investigado por SSH el método real de Odoo 18.0-20260513
  (`SaleOrder._program_check_compute_points`) antes de escribir el
  cambio (regla 5) — no se reescribió esa lógica compleja, solo se
  recorta el conjunto de líneas que le llegan como entrada.
- 2026-09-10: Fix del default de "Incluye ITBMS" — estaba encendido (True)
  por defecto para un cliente sin historial, y eso confundía a los
  vendedores (el 99% de los clientes de Andrés NO quiere ITBMS). Ahora el
  default es apagado (False): `custom_itbms_required` en `sale.order`,
  `includes_itbms` en el wizard, y `_last_itbms_choice_for_partner`
  (cuando el cliente no tiene historial) — los tres cambiaron de True a
  False. Se sigue precargando encendido SOLO si ese cliente específico ya
  lo tuvo encendido en un pedido anterior (sin tocar esa parte de la
  lógica, solo el fallback).
- 2026-10-07: REDISEÑO "VERSIÓN H" (tienda completa), lote A = etapas 0-2, v18.0.3.0.0. Diseño en el
  lienzo claude.ai/artifact/3EHWT6Gt3saSMwWaJTDcTr. Todo lo nuevo vive bajo la clase `dkh` del
  <body> y SOLO se ve en vista previa: entrar a `/dkh` (cookie en ese navegador; `/dkh?off=1` la
  apaga) o poner el parámetro del sistema `dkh.enabled` = 1 (todos). Etapa 0: línea base en
  `scripts/tienda_backup/BASELINE_2026-10-07/` (LEEME.md, vista 3329, capturas). Etapa 1: encabezado
  H con buscador + botón QR, pie H, `views/dkh_layout.xml`, `static/src/css/dkh.css`,
  `static/src/js/dkh_shell.js`, `models/website_dkh.py` (`website.dkh_active()`), `controllers/
  dkh_preview.py`. Etapa 2: reglas de cantidad en el SERVIDOR (`models/dkh_rules.py`): mínimo 6,
  tintes NNP al múltiplo de 5 más cercano (22→20, 23→25), solo pedidos con `website_id`;
  `sale.order._cart_update` las aplica y `/shop/dk/set_qty` también; `shop_live_cart.js` ya
  selecciona al tocar y respeta `data-min`/`data-step`. Pedido mínimo B/. 150 (`dkh.min_order`):
  existe `_dkh_min_missing()`; el bloqueo al confirmar entra en la etapa 6. Pendiente de Andrés:
  HTTPS para la cámara (web.base.url hoy es http://).
- 2026-10-07 (noche): Lote A desplegado y probado por Andrés (QR con cámara OK: `BarcodeDetector` +
  respaldo `@zxing/library`; `clean_url()` no existe en este Odoo → usar `menu.url`). LOTE B =
  etapas 3-5, v18.0.3.1.0: modelo `dkh.banner` (Ventas → Configuración → "Banners de la tienda";
  espacios hero/mid/small/square/tall/shop_top; sin imagen se ve el diseño pastel con título y
  subtítulo), `views/dkh_home.xml` (Inicio H inyectado al final de `<main>` solo en `/dkh`, el
  Inicio viejo se oculta por CSS `body.dkh-home #wrap`; la vista website.inicio NO se toca),
  cintillo de marcas (parámetro `dkh.brands`, coma), `static/src/css/dkh_pages.css` (Inicio,
  Tienda y Producto en estilo H, todo bajo `.dkh`), carrusel del banner principal en `dkh_shell.js`.
- 2026-10-07 (noche): Lote B probado por Andrés ("todo perfecto"). LOTE C = etapas 6-8, v18.0.3.2.0:
  `controllers/dkh_checkout.py` (`/shop/dk/confirmar` = guarda Forma de Pago/Fecha especial/ITBMS
  en la COTIZACIÓN y exige pedido mínimo `dkh.min_order`; `/shop/dk/gracias`; `/shop/dk/scan` = el
  escáner agrega el producto al pedido), `views/dkh_cart.xml` (panel "confirma tu pedido" bajo el
  carrito, solo vista previa; el botón nativo "Finalizar compra" se oculta por CSS bajo `.dkh`, la
  ruta nativa /shop/checkout NO se bloquea todavía), Pedido rápido v2 (`dkh.quick.alias` = memoria
  por cliente, sugerencias hasta 3 ordenadas por historial de compra, "No es este", etiqueta
  "cantidad ajustada"). Pendiente: etapa 9 (pedido por foto con IA), 10 (pruebas y cambio) y 11.
- 2026-10-08: Ajustes tras probar el Lote C (v18.0.3.3.0). (1) Carrito en vivo: `dkh_cart.js` toma el
  control de +/−/escribir/quitar en `.dk-cline` (fase de captura), llama `/shop/dk/set_qty` y
  reemplaza las piezas del carrito (líneas, resumen, barra) sin refrescar. (2) Se QUITÓ el panel de
  Forma de Pago/Fecha especial/ITBMS del carrito y la ruta `/shop/dk/confirmar`: eso es de la venta
  en ruta; los clientes de la web SIEMPRE pagan ITBMS 7% y con tarjeta o transferencia, así que
  "Finalizar compra" sigue el flujo NATIVO de Odoo (solo se habilita con el pedido mínimo).
  (3) `action_confirm`: en pedidos de la web con pago en línea se llena solo la forma de pago
  (transferencia si el proveedor es `custom`, si no tarjeta) e ITBMS sí, sin abrir el pop-up de ruta.
  (4) `_check_cart_is_ready_to_be_paid` exige el pedido mínimo en el servidor con la H encendida
  (si este Odoo no trae ese método, no tiene efecto). Hoy NO hay `payment.provider` activo.
- 2026-10-08: Menú H = "Opción C" elegida por Andrés (v18.0.3.4.0, diseño en el lienzo
  claude.ai/artifact/6tmeuj5KZ5BzGEmWT5qWDa). Computadora: cápsula azul oscuro con la sección activa en
  blanco (items de `website.menu`). Tablet (≤1024): riel lateral fijo de 96 px (`.dkh-dock`, `#wrapwrap`
  con padding-left). Celular (≤640): barra inferior con botón central "Escanear" y hoja "Más"
  (Contáctanos / Mis pedidos / Mi cuenta / WhatsApp, `#dkh-more`). Se quitó el menú hamburguesa y el
  cajón. Los enlaces del dock son fijos (/, /shop, /pedido-rapido, /contactus), no salen de website.menu.
- 2026-10-08: Ajustes v18.0.3.5.0. (1) Cantidades: el carrito (`dkh_cart.js`) y las tarjetas
  (`shop_live_cart.js`) esperan 900 ms tras el último toque de +/− y mandan UNA sola actualización.
  (2) "Nuevos" (`_dk_new_products`) ya NO exige categoría web (los productos recién creados, de julio,
  no la tienen): el Inicio H los muestra en un carrusel deslizable de hasta 12. (3) "Lo más pedido" del
  Inicio H = `_dk_bestsellers_by_category`: el más vendido (90 días) de cada categoría raíz, en orden de
  ventas. (4) En las filas de categorías deslizables (`.dk-chips`) la elegida se acerca al principio.
- 2026-10-08: LOTE D parte 1 (v18.0.3.6.0). (1) Reglas de cantidad nuevas en `rule_for()` (`dkh_rules.py`, solo
  pedidos web): ALISET ...69GR = de 12 en 12 (mín. 12); DECOLORANTE = de 12 en 12 (hoy no hay ninguno
  publicado); GODREJ POCKET (o AER POCKET) = de 6 en 6. Cualquier cantidad se redondea al múltiplo más cercano
  (empate hacia arriba). (2) Pedido rápido por FOTO (solo con `/dkh`): `/pedido-rapido/foto` reduce las fotos en
  memoria (no se guardan), las manda a Claude (`claude-haiku-4-5`, librería `anthropic`, clave en la variable
  de entorno `ANTHROPIC_API_KEY` del contenedor, NUNCA en el repo) y devuelve el texto que alimenta el mismo
  revisor del modo escribir. Sin clave o sin librería responde 503 con un aviso amable. `deploy.sh` paso 5
  instala `anthropic` en el contenedor nuevo (se pierde si EasyPanel recrea el contenedor sin deploy).
- 2026-10-08: v18.0.3.7.0 / 3.8.0. Avisos de regla de cantidad (`dkRuleMsg`/`dkToast` en shop_live_cart.js): al bajar
  del mínimo NO se quita el producto (se avisa; quitar = escribir 0 o "Quitar" en el carrito) y al escribir una
  cantidad que se ajusta sale el aviso. Encabezado H fijo (`.dkh-bar`, sticky): se esconde al bajar y reaparece al
  subir (escucha scroll de `window` y de `#wrapwrap`); el botón dice "Carrito" + cantidad de productos
  (`.dkh-cart-count`, líneas del pedido, se actualiza en vivo); la píldora flotante `.dk-pill` se oculta bajo `.dkh`;
  `window.dkFly(elemento)` hace volar la foto del producto hacia el carrito al agregar (tarjetas, Pedido rápido).
- 2026-10-08: ACTIVADA y luego DESACTIVADA la Versión H. `dkh.enabled` (ir.config_parameter id 66) se creó en 1 (v18.0.3.8.2) y
  se puso en 0 el mismo día: a Andrés no le gustó el diseño H. El código H NO se borra (sigue como alternativa, visible solo
  entrando por /dkh); se reactiva con `dkh.enabled` = 1. Decisión: nueva "VERSIÓN I" = el diseño ANTERIOR a la H (azul oscuro
  #0B1F3A / negro / blanco, Manrope, esquinas discretas) refinado, con TODAS las funciones de la H (cintillo de marcas, menú
  app: barra inferior en celular, riel en tablet, barra superior en computadora; encabezado fijo; Carrito con número de
  productos distintos; reglas de cantidad y avisos; escáner; Pedido rápido con foto/sugerencias; animaciones). Se reutiliza la
  lógica (JS, controladores, modelos) y solo cambia la piel. Colores, tipografía y formas = los del diseño anterior (NO cambian); la redacción de los textos (palabras que ve el cliente) = la de la H. Trabajo por lotes de 3 con plan
  previo y vista previa privada.
- 2026-10-08: VERSIÓN I, LOTE 1 (v18.0.4.0.0). Se activa con la vista previa `/dki` (cookie `dki_preview`, `/dki?off=1` la apaga) o
  el parámetro `dki.enabled` = 1 (todos). `website.dki_active()`; `dkh_active()` devuelve True también cuando la I está activa (la
  estructura y las funciones son las de la H); el body lleva `dkh dki`. La piel vive en `static/src/css/dki.css` (carga DESPUÉS de
  dkh.css/dkh_pages.css, todo bajo `body.dki`): redefine las variables `--dkh-*` (azul oscuro #0B1F3A, grises, Manrope, acento
  azul) y las formas (esquinas 8–10 px, botones sobrios, tarjetas blancas con borde fino). Menú: computadora = barra con la
  sección activa subrayada; tablet = riel; celular = barra inferior. Pendiente: Lote 2 (Inicio, Tienda, Producto) y Lote 3
  (Carrito, Pedido rápido, pruebas, cambio). Si ambas (`dkh.enabled` y `dki.enabled`) están en 1, gana la I.
- 2026-10-08: Versión I: con la I activa el Inicio es el ANTERIOR (vista website.inicio), no el Inicio H (`dkh_home` y la clase
  `dkh-home` solo salen cuando `dki_active()` es falso). La I = páginas anteriores + encabezado/menú app/avisos/animaciones/funciones.
- 2026-10-08: Versión I (v18.0.4.0.2): las reglas de PÁGINAS de `dkh_pages.css` que dan el aspecto H (tarjetas pastel, píldoras,
  títulos gigantes, Tienda/Producto/Carrito) ahora van con `.dkh:not(.dki)`: con la I activa se ve el diseño ANTERIOR de esas
  páginas (shop_live_cart.css + shop_redesign.css) y solo se suman encabezado, menú app, funciones, avisos y animaciones.
  `dki.css` ya no re-pinta tarjetas/botones antiguos: solo piezas nuevas y el Pedido rápido.
- 2026-10-08: VERSIÓN I, LOTE 2 (v18.0.4.1.0). Inicio con la I: al final de `dk_home_hero` (website_home_hero.xml, `t-if website.dki_active()`)
  se agregan cintillo de marcas (`dkh.brands`), banners editables mid/small (`dkh.banner`, solo si existen o si es administrador),
  "Nuevos productos" (carrusel, `_dk_new_products(12)`) y "Lo más pedido" (`_dk_bestsellers_by_category(8)`); el "Nuevos" viejo de
  website.inicio (vista de BD 3328, NO editada) se oculta por CSS `section:has(> .dk-snap)`. `dkh_slot` acepta `only_real` (sin
  diseño de ejemplo para clientes). Tienda (todas las versiones): su "Lo más pedido" ahora es `_dk_bestsellers_by_category(4)`.
- 2026-10-08: Fix tablet (v18.0.4.1.1): en 641–900 px (iPad mini/Air/Pro 11) el banner del Inicio usaba `100vw` a todo el ancho de la
  pantalla, pero con el riel lateral (96 px, `#wrapwrap` con padding-left) se salía 48 px a cada lado y se cortaba. `dki.css` lo calcula
  como `calc(100vw - 96px)` con margen compensado. Verificado con navegador real contra la tienda en 744/768/810/820/834/1024 px.
- 2026-10-08: v18.0.4.2.0. (1) Cinta del Inicio (Versión I): de borde a borde (`.dki-ribbon`, ancho `100vw` menos el riel en tablet),
  sin esquinas, movimiento continuo sin hueco (dos mitades iguales, cada una con ≥14 elementos), se pausa al pasar el mouse. Muestra los
  PRODUCTOS CON PROMOCIÓN (`product.template._dk_promo_products`: programas `buy_x_get_y` activos, hasta 3 por programa, solo el nombre,
  enlazado al producto); sin promociones muestra las marcas (`dkh.brands`). (2) Botón Eliminar: al agregar un producto, el estado "en el
  carrito" muestra − cantidad + y un botón de texto "Eliminar" (`.dk-del`, quita el producto); en el carrito el enlace "Quitar" pasó a ser
  el mismo botón (`.js_delete_product.dk-del`). Bajar del mínimo solo avisa ("usa Eliminar").
- 2026-10-08: Fix (v18.0.4.2.1): en el Inicio, el CSS inline de la vista website.inicio (`#dk-home .dk-add { display: flex }`) pisaba la regla
  `.dk-buy[data-state="in"] .dk-add { display: none }` y el botón Agregar seguía visible tras agregar. `shop_live_cart.css` ahora lleva las
  mismas reglas con `#dk-home` delante. Verificado con navegador real contra la tienda (respuesta del carrito simulada, sin tocar la BD).
- 2026-10-08: v18.0.4.2.2: la cinta de promociones del Inicio (Versión I) pasó ARRIBA del bloque 1 (banner), pegada al encabezado, no
  entre el banner y "Nuevos". Orden del Inicio I: cinta · banner + servicios · banners editables · Nuevos · Lo más pedido · categorías · marcas.

