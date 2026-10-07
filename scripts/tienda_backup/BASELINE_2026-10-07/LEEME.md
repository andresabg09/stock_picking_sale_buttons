# Línea base de la tienda — 2026-10-07 (Etapa 0 del rediseño "Versión H")

Foto del estado de producción ANTES de empezar el rediseño. Sirve para revertir.
Nada de esto se modificó ni se borró: es solo lectura (MCP) + capturas.

## Dónde vive la tienda actual (base `shalom`, sitio 1 "SHALOM PANAMÁ")

| Registro | id | Qué es | Respaldo en el repo |
| --- | --- | --- | --- |
| `ir.ui.view` `website.inicio` | 3328 | Inicio actual (`/inicio`) | `../NEW_inicio_view3328_banners_final.xml` |
| `ir.ui.view` `website.dianke_theme` | 3329 | Tema: CSS global + barra superior (fuerza texto negro con `!important` dentro de `main`) | `VISTA_3329_tema.xml` (esta carpeta) |
| `ir.ui.view` `website.dianke_footer` | 3330 | Pie de página | `../PREVIOUS_footer_view3330.xml` |
| `ir.ui.view` `website.dianke_header_search` | 3331 | Buscador del encabezado | `../PREVIOUS_header_search_view3331.xml` |
| `website.page` | 11 | `/inicio` publicada (vista 3328) | — |
| `website.page` | 8, 9, 10 | Inicio antiguo (`/shalom`, `/archivada`) despublicado | — |
| `website.menu` | 5, 7, 9, 6 | Menú: Inicio `/`, Tienda `/shop`, Pedido rápido `/pedido-rapido`, Contáctanos `/contactus` | — |
| `ir.config_parameter` | 65 | `stock_picking_sale_buttons.new_days` = 120 | — |
| `ir.config_parameter` | 4 | `web.base.url` = `http://shalom-odoo.cjauws.easypanel.host` (**sin HTTPS**) | — |
| Paleta | — | `ir.attachment` 36083 / 27478 | `../ORIGINAL_user_*.scss` y `../NEW_user_*.scss` |
| `website.custom_code_head` | 1 | Reemplazado por un comentario | `../ORIGINAL_website_custom_code_head.html` |

Capas del layout que el rediseño tocará (solo por herencia, sin reemplazarlas):
`website.layout` (vista 1013) → `<header id="top">`, `<main>`, `<footer id="bottom">` con `<div id="footer">`;
la clase del `<body>` sale de la variable `body_classname` de `web.layout` (vista 180).

## Hallazgos que condicionan el plan

1. **HTTPS:** `web.base.url` empieza con `http://`. La cámara (escáner y foto) exige HTTPS.
2. **Tema 3329:** fuerza texto negro con `!important` a casi todo dentro de `main`. Todo el CSS nuevo irá bajo `.dkh` y, en vista previa, neutraliza ese bloque.
3. **El código de Odoo no se puede leer desde aquí** (solo datos por MCP). Los nombres de métodos nativos que no se vean en las vistas se verifican antes de usarse.

## Capturas (carpeta `capturas/`)
Inicio, tienda, ficha de producto (`/shop/shp-kristell-500ml-maca-collagen-8541`) y carrito, en 1440 px (`pc`), 820 px (`tablet`) y 390 px (`celular`). Pedido rápido no se captura: requiere sesión.

## Cómo revertir cualquier etapa
- Código: `git revert` del commit del lote.
- Vista previa: borrar la cookie visitando `/dkh?off=1` o poner `dkh.enabled` = 0.
- Registros de la base: este respaldo contiene el XML original de cada vista; solo se restauran con confirmación de Andrés.
