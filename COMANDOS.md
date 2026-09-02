# Comandos armados, pedido por pedido

Todo lo que hace `verificar.sh`, pero como comandos sueltos para copiar y pegar. Sirve para
mostrar en vivo, para que los profesores prueben con `curl` sin correr ningún script, y para
entender qué chequea cada paso. Cada bloque es independiente del anterior salvo donde se dice.

Sólo hace falta `curl`. Donde aparece `jq` es comodidad, no requisito: al lado está la variante
sin `jq`.

Si levantaste la demo en otro puerto, cambiá `localhost:8080` por el que usaste
(`PUERTO_PROXY`).

---

## 0. La demo está levantada

```bash
curl -s localhost:8080/health
```

```
{"instancia":"app1","estado":"ok"}
```

Las dos instancias, directo y sin pasar por el proxy:

```bash
curl -s localhost:3001/health; echo; curl -s localhost:3002/health; echo
```

---

## 1. Seguridad: autenticar actores

**Sin token → 401.** El pedido ni siquiera llega a la lógica de ruteo.

```bash
curl -si -X PUT localhost:8080/api/equipaje/123/ruta -H 'Content-Type: application/json' -d '{"ruta":"cinta-7"}' | head -1
```

```
HTTP/1.1 401 Unauthorized
```

**Password incorrecta → 401.**

```bash
curl -si -X POST localhost:8080/auth/login -H 'Content-Type: application/json' -d '{"usuario":"operador","password":"incorrecta"}' | head -1
```

**Login del operador → 200 + token.** Guardarlo en una variable para los pasos siguientes:

```bash
TOKEN_OP=$(curl -s -X POST localhost:8080/auth/login -H 'Content-Type: application/json' -d '{"usuario":"operador","password":"1234"}' | jq -r .token); echo "${TOKEN_OP:0:25}..."
```

Sin `jq` (recorta el token a mano de la respuesta):

```bash
TOKEN_OP=$(curl -s -X POST localhost:8080/auth/login -H 'Content-Type: application/json' -d '{"usuario":"operador","password":"1234"}' | sed 's/.*"token":"\([^"]*\)".*/\1/'); echo "${TOKEN_OP:0:25}..."
```

**Login del supervisor → 200 + token.**

```bash
TOKEN_SUP=$(curl -s -X POST localhost:8080/auth/login -H 'Content-Type: application/json' -d '{"usuario":"supervisor","password":"1234"}' | sed 's/.*"token":"\([^"]*\)".*/\1/'); echo "${TOKEN_SUP:0:25}..."
```

---

## 2. Seguridad: autorizar actores

Mismo endpoint, mismo sistema, distinta identidad. Eso es lo que separa a las dos tácticas.

**Token de operador → 403.** Está autenticado, pero su rol no puede modificar rutas.

```bash
curl -s -X PUT localhost:8080/api/equipaje/123/ruta -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN_OP" -d '{"ruta":"cinta-7"}'
```

```
{"error":"rol sin permiso para esta operación","rolDelActor":"operador","rolesRequeridos":["supervisor"]}
```

**Token de supervisor → 200.**

```bash
curl -s -X PUT localhost:8080/api/equipaje/123/ruta -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN_SUP" -d '{"ruta":"cinta-7"}'
```

```
{"instancia":"app1","equipaje":"123","rutaNueva":"cinta-7","modificadaPor":"supervisor"}
```

---

## 3. Disponibilidad: el artefacto de evidencia (headers del proxy)

Con poca carga aparece **una sola IP** y **un solo estado**: todo lo atiende el primario.

```bash
curl -si localhost:8080/api/equipaje/1/scan -H "Authorization: Bearer $TOKEN_OP" | grep '^X-'
```

```
X-Instancias-Probadas: 172.18.0.3:3000
X-Estados: 200
X-Tiempo-Total: 0.306
```

El contador de app2 tiene que estar en **cero** antes del pico. Ese cero es la evidencia de que
el repuesto está *warm*: encendido pero sin tráfico.

```bash
curl -s localhost:3002/stats
```

```
{"instancia":"app2","maxConcurrentes":100,"enVuelo":0,"atendidos":0,"rechazados":0}
```

---

## 4. Disponibilidad: reintentos + repuesto redundante

**Veinte pedidos en paralelo, en un solo comando.** `curl` desde la versión 7.66 acepta
`--parallel` y el rango `[1-20]` en la URL: no hace falta un `for` ni un script. app1 admite 5
pedidos a la vez; del sexto en adelante responde 503, Nginx reintenta contra app2 y el cliente
recibe 200 igual.

```bash
curl -sZ --parallel-max 20 -o /dev/null -D - -H "Authorization: Bearer $TOKEN_OP" "localhost:8080/api/equipaje/[1-20]/scan" | grep -i '^X-Estados' | sort | uniq -c
```

```
   6 X-Estados: 200
  14 X-Estados: 503, 200
```

Lectura: 5 o 6 los atendió app1 (`200`); los demás llegaron mientras app1 estaba llena, fueron
rechazados con 503 y reintentados contra app2 **en el mismo pedido** (`503, 200`). Los números
exactos varían de corrida en corrida; lo que no varía es que **ninguna respuesta terminó en
error**. Si el pico se dispara más despacio, Nginx alcanza a marcar caída a app1 (`max_fails=2`)
y las últimas respuestas salen `200` directo del repuesto.

Para ver la respuesta completa que muestra el reintento **y** el failover **y** el tiempo que
tardó, en tres líneas:

```bash
curl -sZ --parallel-max 20 -o /dev/null -D - -H "Authorization: Bearer $TOKEN_OP" "localhost:8080/api/equipaje/[1-20]/scan" | grep -i '^X-' | grep -B1 -A1 ', 200'
```

```
X-Instancias-Probadas: 172.18.0.3:3000, 172.18.0.2:3000
X-Estados: 503, 200
X-Tiempo-Total: 0.002, 0.309
```

`X-Tiempo-Total` es el criterio **CA-1** medido: el primario tardó 2 ms en rechazar y el
repuesto 309 ms en responder. Conmutación muy por debajo de los 2 s.

Si el `curl` de la máquina es viejo y no tiene `--parallel`, el bucle equivalente:

```bash
for i in $(seq 1 20); do curl -s -o /dev/null -D - localhost:8080/api/equipaje/$i/scan -H "Authorization: Bearer $TOKEN_OP" & done; wait
```

**El contador de app2 despegó.** Antes era cero:

```bash
curl -s localhost:3002/stats
```

```
{"instancia":"app2","maxConcurrentes":100,"enVuelo":0,"atendidos":15,"rechazados":0}
```

**El primario también cuenta lo que rechazó:**

```bash
curl -s localhost:3001/stats
```

---

## 5. Disponibilidad: recuperación del primario

Nginx marca caído a app1 durante `fail_timeout=10s`. Pasado ese tiempo vuelve a probarlo y el
tráfico regresa solo, sin intervención manual. Esperar 11 s y repetir el pedido del paso 3:

```bash
sleep 11; curl -si localhost:8080/api/equipaje/1/scan -H "Authorization: Bearer $TOKEN_OP" | grep -E '^X-|instancia'
```

```
X-Instancias-Probadas: 172.18.0.3:3000
X-Estados: 200
X-Tiempo-Total: 0.304
{"instancia":"app1",...}
```

---

## 6. Pico de carga de 60 s (k6) sin instalar nada

El escenario hace el login solo. El panel de k6 queda en http://localhost:5665 mientras corre.

```bash
docker compose --profile carga run --rm --service-ports k6
```

Al final, k6 imprime el resumen. Las líneas que hay que leer en voz alta:

```
█ THRESHOLDS
  checks             ✓ 'rate>0.99'   rate=100.00%
  http_req_duration  ✓ 'p(95)<2000'  p(95)=309.73ms   ← CA-1: conmutar en menos de 2 s
  http_req_failed    ✓ 'rate<0.01'   rate=0.00%       ← el cliente nunca vio un error
CUSTOM
  atendidos_por_app1.: 164
  atendidos_por_app2.: 4756                           ← el repuesto absorbió el pico
  conmutaciones......: 18                             ← respuestas con "503, 200"
```

Por qué `conmutaciones` es chico: con dos rechazos seguidos Nginx marca caída a app1 durante
10 s y manda todo directo al repuesto (`X-Estados: 200`, sin reintento). Cada 10 s vuelve a
probar el primario, que acepta cinco, rechaza dos, y el ciclo se repite. Lo que importa es
`http_req_failed: 0.00%`.

Con k6 instalado en la máquina es lo mismo sin Docker:

```bash
K6_WEB_DASHBOARD=true k6 run carga/escenario.js
```

---

## 7. Reiniciar los contadores entre ensayos

Sin tocar los contenedores:

```bash
curl -s -X POST localhost:3001/stats/reset; echo; curl -s -X POST localhost:3002/stats/reset; echo
```

```
{"instancia":"app1","maxConcurrentes":5,"enVuelo":0,"atendidos":0,"rechazados":0}
{"instancia":"app2","maxConcurrentes":100,"enVuelo":0,"atendidos":0,"rechazados":0}
```

Con eso app2 vuelve a cero y el efecto "despega desde cero" se ve igual que la primera vez.
Después de un pico, esperar 11 s antes del siguiente ensayo (Nginx tiene a app1 marcada
como caída durante `fail_timeout=10s`).
