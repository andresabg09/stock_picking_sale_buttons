#!/bin/bash
# limpiar_duplicados.sh — Borra productos archivados duplicados SIN historial (ver limpiar_duplicados.py).
# Uso:  sudo bash limpiar_duplicados.sh            (simulacro: no cambia nada)
#       sudo bash limpiar_duplicados.sh --apply    (borra de verdad)
# Deja un respaldo de lo borrado en /root/respaldos_odoo/ (fuera del repo, trae costos).
set -e
REPO_DIR="/root/odoo-addons/stock_picking_sale_buttons"
DB="shalom"
APPLY=0
[ "$1" = "--apply" ] && APPLY=1
CID=$(docker ps --filter "name=crm_odoo." --format "{{.Names}}" | head -n1)
if [ -z "$CID" ]; then echo "ERROR: no se encontró el contenedor crm_odoo"; exit 1; fi
DB_HOST=$(docker exec "$CID" printenv HOST)
DB_PORT=$(docker exec "$CID" printenv PORT)
DB_USER=$(docker exec "$CID" printenv USER)
DB_PASS=$(docker exec "$CID" printenv PASSWORD)
mkdir -p /root/respaldos_odoo
LOG="/root/respaldos_odoo/limpiar_duplicados_$(date +%Y%m%d_%H%M%S)_$([ $APPLY = 1 ] && echo aplicado || echo simulacro).log"
docker exec -i -e APPLY=$APPLY "$CID" odoo shell -d "$DB" --no-http \
  --db_host="$DB_HOST" --db_port="$DB_PORT" --db_user="$DB_USER" --db_password="$DB_PASS" \
  < "$REPO_DIR/scripts/limpiar_duplicados.py" 2>&1 | grep -v -E "INFO|WARNING" | tee "$LOG"
echo "Registro guardado en: $LOG"
