#!/bin/bash
# setup_server_git.sh — Configuración ÚNICA (correr solo una vez).
# Convierte la carpeta del módulo en el servidor en un checkout de git
# conectado a GitHub, respaldando primero lo que hay actualmente.
set -e

TARGET="/root/odoo-addons/stock_picking_sale_buttons"
BACKUP="/root/odoo-addons/stock_picking_sale_buttons.backup.$(date +%Y%m%d%H%M%S)"
REPO_URL="https://github.com/andresabg09/stock_picking_sale_buttons.git"

echo "== Respaldando carpeta actual =="
mv "$TARGET" "$BACKUP"
echo "Backup guardado en: $BACKUP"

echo "== Clonando repositorio desde GitHub =="
git clone "$REPO_URL" "$TARGET"

echo "== Listo =="
echo "El módulo ahora vive en $TARGET y está conectado a GitHub."
echo "De ahora en adelante, usa scripts/deploy.sh para actualizar."
echo "(El backup en $BACKUP puedes borrarlo una vez confirmes que todo funciona bien.)"
