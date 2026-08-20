#!/bin/bash
# recon.sh — Reconocimiento rápido del entorno Odoo en el servidor.
# Correr esto por SSH en la VM y pegar TODA la salida en el chat.
# Detecta en un solo paso: contenedor de Odoo, variables de entorno de BD,
# ruta del módulo dentro del contenedor, y el archivo de configuración odoo.conf.

echo "== Contenedores activos =="
docker ps --format "{{.Names}} | {{.Image}} | {{.Status}}"

CID=$(docker ps --format "{{.Names}} {{.Image}}" | grep -i odoo | awk '{print $1}' | head -n1)
echo
echo "== Contenedor de Odoo detectado: ${CID:-NO_DETECTADO} =="

if [ -n "$CID" ]; then
  echo
  echo "== Variables de entorno relacionadas a BD/Odoo =="
  docker exec "$CID" env 2>/dev/null | grep -iE 'DB_|POSTGRES|ODOO'

  echo
  echo "== Ruta del módulo stock_picking_sale_buttons dentro del contenedor =="
  docker exec "$CID" find / -maxdepth 8 -iname "stock_picking_sale_buttons" -not -path "*/proc/*" 2>/dev/null

  echo
  echo "== Archivo(s) odoo.conf encontrados =="
  docker exec "$CID" find / -maxdepth 6 -iname "odoo.conf" -not -path "*/proc/*" 2>/dev/null
fi
