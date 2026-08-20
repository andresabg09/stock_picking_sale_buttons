#!/bin/bash
# deploy.sh — Despliegue rutinario del módulo stock_picking_sale_buttons.
# Requiere haber corrido setup_server_git.sh una vez antes.
# Orden: 1) traer código nuevo y verificar  2) permisos  3) actualizar módulo  4) reiniciar
# NOTA: /root/odoo-addons pertenece a root — correr con: sudo bash deploy.sh
set -e

REPO_DIR="/root/odoo-addons/stock_picking_sale_buttons"
SERVICE="crm_odoo"
DB="shalom"
MODULE="stock_picking_sale_buttons"

echo "== 1/4: Trayendo el código más reciente de GitHub =="
cd "$REPO_DIR"
git pull origin master
echo "Último commit aplicado:"
git log -1 --oneline

echo
echo "== 2/4: Verificando permisos de la carpeta =="
ls -la "$REPO_DIR" | head -5
# Si el contenedor no logra leer los archivos tras el pull, correr manualmente:
#   chown -R root:root "$REPO_DIR"

echo
echo "== 3/4: Actualizando el módulo dentro de Odoo (BD: $DB) =="
CID=$(docker ps --filter "name=${SERVICE}." --format "{{.Names}}" | head -n1)
if [ -z "$CID" ]; then
  echo "ERROR: no se encontró el contenedor del servicio $SERVICE"
  exit 1
fi
docker exec "$CID" odoo -u "$MODULE" -d "$DB" --stop-after-init

echo
echo "== 4/4: Reiniciando el servicio Odoo (para recargar el código Python) =="
docker service update --force "$SERVICE"

echo
echo "Listo. Para ver que arrancó bien:"
echo "  docker service logs ${SERVICE} --tail 100 -f"
