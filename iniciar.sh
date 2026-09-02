#!/usr/bin/env bash
# Levanta la demo (nginx + app1 + app2) y espera a que el proxy responda.
#
#   ./iniciar.sh                              puertos 8080 (proxy) / 3001 (app1) / 3002 (app2)
#   PUERTO_PROXY=18080 ./iniciar.sh           si 8080 está ocupado
#   PERFIL=observabilidad ./iniciar.sh        además Prometheus (9090) + Grafana (3003)
set -euo pipefail
cd "$(dirname "$0")"

# El plugin `docker compose` o el binario `docker-compose`, el que exista en la máquina.
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi

$DC ${PERFIL:+--profile "$PERFIL"} up --build -d

BASE="http://localhost:${PUERTO_PROXY:-8080}"
printf 'Esperando al proxy en %s ' "$BASE"
for _ in $(seq 1 30); do
  if curl -sf "$BASE/health" >/dev/null 2>&1; then break; fi
  printf '.'; sleep 1
done
echo
if ! curl -sf "$BASE/health" >/dev/null 2>&1; then
  echo "El proxy no respondió en 30 s. Mirar: $DC logs nginx" >&2
  exit 1
fi

echo "proxy : $BASE/health  ->  $(curl -s "$BASE/health")"
echo "app1  : http://localhost:${PUERTO_APP1:-3001}/stats"
echo "app2  : http://localhost:${PUERTO_APP2:-3002}/stats"
if [ "${PERFIL:-}" = "observabilidad" ]; then
  echo "grafana: http://localhost:${PUERTO_GRAFANA:-3003}   (abre directo en el tablero, sin login)"
fi
echo
echo "Listo. Para verificar las cuatro tácticas:"
echo "  - Postman: importar postman/AeroSur-TFU.postman_collection.json y correr la colección"
echo "  - Sin Postman: $DC --profile verificacion run --rm newman"
echo "  - A mano, pedido por pedido: COMANDOS.md"
