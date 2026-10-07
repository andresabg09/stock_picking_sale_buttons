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
# HOST/USER/PASSWORD/PORT ya existen como variables de entorno DENTRO del
# contenedor (las pone EasyPanel al crearlo). Se leen aquí en variables de
# shell temporales (solo viven en esta ejecución, nunca se escriben a disco
# ni a git) para pasarlas explícitas al comando de actualización.
DB_HOST=$(docker exec "$CID" printenv HOST)
DB_PORT=$(docker exec "$CID" printenv PORT)
DB_USER=$(docker exec "$CID" printenv USER)
DB_PASS=$(docker exec "$CID" printenv PASSWORD)
docker exec "$CID" odoo -u "$MODULE" -d "$DB" --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASS" --stop-after-init

echo
echo "== 4/4: Reiniciando el servicio Odoo (para recargar el código Python) =="
docker service update --force "$SERVICE"

echo
echo "== 5/5: Asegurando la librería 'anthropic' (modo foto del Pedido rápido) =="
# El contenedor se recrea en el paso 4, así que se instala en el contenedor NUEVO. No es crítico:
# si falla, el resto de la tienda funciona y solo el modo foto avisa que no está instalado.
set +e
NEW=""
for i in $(seq 1 30); do
  NEW=$(docker ps --filter "name=${SERVICE}." --format "{{.Names}}" | head -n1)
  if [ -n "$NEW" ] && [ "$NEW" != "$CID" ] && docker exec "$NEW" true 2>/dev/null; then break; fi
  sleep 2
done
if [ -n "$NEW" ]; then
  if docker exec "$NEW" python3 -c "import anthropic" 2>/dev/null; then
    echo "anthropic ya está instalada."
  else
    docker exec "$NEW" pip install --quiet anthropic 2>/dev/null \
      || docker exec "$NEW" pip install --quiet --break-system-packages anthropic 2>/dev/null \
      && echo "anthropic instalada." || echo "AVISO: no se pudo instalar anthropic (el modo foto quedará apagado)."
  fi
fi
set -e

echo
echo "Listo. Para ver que arrancó bien:"
echo "  docker service logs ${SERVICE} --tail 100 -f"
