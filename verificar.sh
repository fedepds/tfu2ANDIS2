#!/usr/bin/env bash
# Chequeo corrible del checklist de la sección 8 del plan, sin abrir Postman.
# Si alguna de las cuatro tácticas se rompe, este script falla.
set -uo pipefail

BASE=${BASE:-http://localhost:8080}
FALLOS=0

ok()    { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
falla() { printf '  \033[31mFALLA\033[0m %s\n' "$1"; FALLOS=$((FALLOS+1)); }

codigo() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

login() {
  curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
    -d "{\"usuario\":\"$1\",\"password\":\"1234\"}" | jq -r '.token // empty'
}

# --- 0. Esperar a que el proxy y las dos instancias respondan ---------------
printf '\nEsperando a que levante la demo...\n'
for i in $(seq 1 30); do
  [ "$(codigo "$BASE/health")" = "200" ] && break
  sleep 1
done
if [ "$(codigo "$BASE/health")" != "200" ]; then
  echo "El proxy no responde en $BASE. ¿Corriste 'docker-compose up -d'?" >&2
  exit 1
fi

# --- 1. Tácticas de seguridad ----------------------------------------------
printf '\nTácticas de seguridad (autenticar / autorizar actores)\n'

C=$(codigo -X PUT "$BASE/api/equipaje/123/ruta" -H 'Content-Type: application/json' -d '{"ruta":"cinta-7"}')
[ "$C" = "401" ] && ok "sin token -> 401 (autenticar)" || falla "sin token -> esperaba 401, dio $C"

C=$(codigo -X POST "$BASE/auth/login" -H 'Content-Type: application/json' -d '{"usuario":"operador","password":"malo"}')
[ "$C" = "401" ] && ok "password incorrecta -> 401 (autenticar)" || falla "password incorrecta -> esperaba 401, dio $C"

TOKEN_OP=$(login operador)
[ -n "$TOKEN_OP" ] && ok "login operador -> 200 + token (autenticar)" || falla "login operador no devolvió token"

TOKEN_SUP=$(login supervisor)
[ -n "$TOKEN_SUP" ] && ok "login supervisor -> 200 + token" || falla "login supervisor no devolvió token"

C=$(codigo -X PUT "$BASE/api/equipaje/123/ruta" -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $TOKEN_OP" -d '{"ruta":"cinta-7"}')
[ "$C" = "403" ] && ok "PUT con token de operador -> 403 (autorizar)" || falla "PUT operador -> esperaba 403, dio $C"

C=$(codigo -X PUT "$BASE/api/equipaje/123/ruta" -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $TOKEN_SUP" -d '{"ruta":"cinta-7"}')
[ "$C" = "200" ] && ok "PUT con token de supervisor -> 200 (autorizar)" || falla "PUT supervisor -> esperaba 200, dio $C"

# --- 2. Headers de evidencia -----------------------------------------------
printf '\nArtefacto de evidencia (headers del proxy)\n'
H=$(curl -s -D - -o /dev/null "$BASE/api/equipaje/1/scan" -H "Authorization: Bearer $TOKEN_OP")
for h in X-Instancias-Probadas X-Estados X-Tiempo-Total; do
  echo "$H" | grep -qi "^$h:" && ok "header $h presente" || falla "falta el header $h"
done
# El header puede estar presente y traer "-": pasa con $upstream_response_time, que todavía
# no tiene valor cuando Nginx manda los headers. Un tiempo sin dígitos no sirve de evidencia.
echo "$H" | grep -i '^X-Tiempo-Total:' | grep -q '[0-9]' \
  && ok "X-Tiempo-Total trae un número, no '-'" \
  || falla "X-Tiempo-Total sin valor: usar \$upstream_header_time, no \$upstream_response_time"

# --- 3. Reintentos + repuesto redundante -----------------------------------
printf '\nTácticas de disponibilidad (reintentos / repuesto redundante)\n'
ANTES=$(curl -s http://localhost:3002/stats | jq -r '.atendidos')

TMP=$(mktemp -d)
for i in $(seq 1 20); do
  curl -s -D "$TMP/h$i" -o /dev/null "$BASE/api/equipaje/$i/scan" \
    -H "Authorization: Bearer $TOKEN_OP" &
done
wait

# Una respuesta con dos valores en X-Estados es el reintento y el failover juntos.
EVIDENCIA=$(grep -hi '^X-Estados:' "$TMP"/h* | grep ',' | head -1)
if [ -n "$EVIDENCIA" ]; then
  ok "hubo conmutación: $(echo "$EVIDENCIA" | tr -d '\r')"
  ok "$(grep -hi '^X-Instancias-Probadas:' "$TMP"/h* | grep ',' | head -1 | tr -d '\r')"
else
  falla "bajo carga ninguna respuesta mostró dos valores en X-Estados"
fi

DESPUES=$(curl -s http://localhost:3002/stats | jq -r '.atendidos')
[ "$DESPUES" -gt "$ANTES" ] \
  && ok "app2 atendió pedidos por primera vez ($ANTES -> $DESPUES)" \
  || falla "el contador de app2 no se movió ($ANTES -> $DESPUES): no hubo failover"
rm -rf "$TMP"

printf '\n'
if [ "$FALLOS" -eq 0 ]; then
  printf '\033[32mTodo verde. La demo está lista.\033[0m\n\n'
else
  printf '\033[31m%s chequeo(s) fallaron.\033[0m\n\n' "$FALLOS"
fi
exit "$FALLOS"
