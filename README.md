# Demo TFU — Tácticas de Arquitectura

**Grupo 5 · Caso AeroSur · PUC-01 Transportar equipaje**

Banco de pruebas que hace observables cuatro tácticas en vivo:

| Táctica | Dónde vive | Qué se ve |
|---|---|---|
| Reintentos | Nginx | Header `X-Estados: 503, 200` |
| Repuesto redundante (*warm*) | Nginx | `X-Instancias-Probadas` con dos IPs + `/stats` de app2 despegando |
| Autenticar actores | `servicio/src/auth.js` | Sin token → `401` |
| Autorizar actores | `servicio/src/auth.js` | Mismo `PUT`: operador → `403`, supervisor → `200` |

El diseño completo, los ADRs y el guion cronometrado están en **`plan-demo-tfu.md`**.

---

## 0. Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Docker + Docker Compose | cualquiera reciente | Levantar los tres contenedores |
| k6 | **≥ 0.49** | Generar la carga y el panel web |
| `jq` y `curl` | — | Extraer el token y correr `verificar.sh` |

```bash
docker --version && k6 version && jq --version
```

> **Ojo con el comando de Compose.** En algunas máquinas `docker compose` (con espacio) no
> está enganchado al CLI. Si te da `unknown command`, usá `docker-compose` con guion —
> es el que funciona en la máquina donde se armó esta demo. Todos los comandos de abajo
> usan la forma con guion.

**Puertos que tienen que estar libres:** `8080` (Nginx), `3001` (app1), `3002` (app2) y
`5665` (panel de k6).

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN      # sin salida = libre
```

---

## 1. Levantar la demo

```bash
docker-compose up --build -d
docker-compose ps                     # deben aparecer tres: nginx, app1, app2
```

La primera vez tarda un par de minutos porque construye la imagen del servicio. **Hacelo el
día anterior**, no delante del tribunal: si el día de la exposición no hay red, las imágenes
ya están en caché local y `docker-compose up -d` (sin `--build`) levanta igual.

Comprobación rápida de que las tres piezas responden:

```bash
curl -s localhost:8080/health | jq    # a través del proxy
curl -s localhost:3001/health | jq    # app1 directo
curl -s localhost:3002/health | jq    # app2 directo
```

---

## 2. Verificar que las cuatro tácticas funcionan

```bash
./verificar.sh
```

Recorre el checklist entero sin abrir Postman: los cinco códigos de seguridad, los tres
headers de evidencia, y —disparando 20 pedidos en paralelo— que hubo conmutación real al
repuesto. Salida esperada:

```
Tácticas de seguridad (autenticar / autorizar actores)
  OK   sin token -> 401 (autenticar)
  OK   password incorrecta -> 401 (autenticar)
  OK   login operador -> 200 + token (autenticar)
  OK   login supervisor -> 200 + token
  OK   PUT con token de operador -> 403 (autorizar)
  OK   PUT con token de supervisor -> 200 (autorizar)

Artefacto de evidencia (headers del proxy)
  OK   header X-Instancias-Probadas presente
  OK   header X-Estados presente
  OK   header X-Tiempo-Total presente
  OK   X-Tiempo-Total trae un número, no '-'

Tácticas de disponibilidad (reintentos / repuesto redundante)
  OK   hubo conmutación: X-Estados: 503, 200
  OK   X-Instancias-Probadas: 10.89.2.23:3000, 10.89.2.22:3000
  OK   app2 atendió pedidos por primera vez (0 -> 15)

Todo verde. La demo está lista.
```

Si algo sale en rojo, la demo **no** está lista. Ver la sección 6.

> Después de correr esto, app1 queda marcada como caída por Nginx durante 10 segundos.
> Esperá ese rato antes de empezar la exposición para que el primer pedido del guion salga
> del primario.

---

## 3. Tácticas de seguridad (Postman)

Importar `postman/AeroSur-Seguridad.postman_collection.json`. Los cinco pedidos van en orden
y los logins guardan el token solos en la variable de colección — **no hay que copiar y pegar
nada en vivo**.

| # | Pedido | Esperado | Táctica |
|---|---|---|---|
| 1 | `PUT /api/equipaje/123/ruta` sin token | `401 falta token` | Autenticar |
| 2 | `POST /auth/login` con `operador/1234` | `200` + token | Autenticar |
| 3 | `PUT` con token de **operador** | `403 rol sin permiso` | Autorizar |
| 4 | `POST /auth/login` con `supervisor/1234` | `200` + token | — |
| 5 | `PUT` con token de **supervisor** | `200 ruta modificada` | Autorizar |

**Lo que hay que decir en el 3 y el 5:** mismo endpoint, mismo sistema, distinta identidad.
Ahí se ve que autenticar y autorizar son dos tácticas distintas.

Usuarios disponibles: `operador/1234` y `supervisor/1234`.

---

## 4. Tácticas de disponibilidad (k6)

### 4.1 Obtener un token para la carga

```bash
TOKEN=$(curl -s -X POST localhost:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"usuario":"operador","password":"1234"}' | jq -r .token)
echo "${TOKEN:0:20}..."     # confirmá que no está vacío
```

Dura una hora; la demo dura cinco minutos.

### 4.2 Mirar los headers en operación normal

```bash
curl -si localhost:8080/api/equipaje/1/scan -H "Authorization: Bearer $TOKEN" | grep '^X-'
```

Con poca carga aparece **una sola IP** y **un solo estado**: todo lo atiende el primario.

```
X-Instancias-Probadas: 10.89.2.23:3000
X-Estados: 200
X-Tiempo-Total: 0.307
```

### 4.3 Preparar la ventana de contadores

En una terminal aparte, dejar corriendo:

```bash
while true; do
  clear
  curl -s localhost:3001/stats | jq -c
  curl -s localhost:3002/stats | jq -c
  sleep 1
done
```

(`watch -n 1 '...'` hace lo mismo en una línea, pero **no viene instalado en macOS**; el
bucle de arriba funciona en cualquier lado. Cortar con `Ctrl-C`.)

`atendidos` de **app2 tiene que estar en cero** antes de arrancar el pico. Ese cero es la
evidencia de que el repuesto está *warm*: encendido pero sin tráfico.

### 4.4 Lanzar la carga

```bash
K6_WEB_DASHBOARD=true k6 run -e TOKEN=$TOKEN carga/escenario.js
```

Panel en **http://localhost:5665**. Dura 60 segundos en tres tramos:

| Tramo | VUs | Qué pasa |
|---|---|---|
| 0–15 s | 5 | Operación normal: un vuelo. Todo lo atiende app1 |
| 15–45 s | 60 | Pico de tres vuelos. app1 satura y empiezan los 503 → conmutación |
| 45–60 s | 5 | Vuelve la normalidad. El tráfico regresa solo al primario |

**Qué señalar mientras corre:**

1. En el panel, la tasa de error subiendo al empezar el pico.
2. En la ventana de contadores, el de **app2 despegando desde cero**.
3. Los headers de una respuesta cualquiera durante el pico — desde otra terminal:

```bash
curl -si localhost:8080/api/equipaje/1/scan -H "Authorization: Bearer $TOKEN" | grep '^X-'
```

```
X-Instancias-Probadas: 10.89.2.33:3000, 10.89.2.31:3000
X-Estados:             503, 200
X-Tiempo-Total:        0.007, 0.310
```

Esas dos líneas son el reintento **y** el failover al repuesto **y** el tiempo que tardó la
conmutación, en una sola respuesta.

### 4.5 Cerrar con los criterios de ajuste

Al terminar, k6 imprime el resumen. Los dos números que hay que leer en voz alta:

- **CA-2 pide tres reintentos.** En pantalla: `proxy_next_upstream_tries 3` en `nginx.conf`.
- **CA-1 pide conmutar en menos de 2 s.** En pantalla: el `p(95)` del resumen de k6 —da del
  orden de **300 ms**— y el segundo valor de `X-Tiempo-Total`.

Una corrida sana termina con `checks_succeeded: 100.00%` y `http_req_failed: 0.00%`: el
cliente **nunca vio un error**, aunque el primario haya rechazado pedidos. Eso *es* la
disponibilidad.

---

## 5. Apagar y reiniciar

```bash
docker-compose restart     # reinicia y pone los contadores de /stats en cero
docker-compose down        # apaga y borra los contenedores
docker-compose down -v     # además borra volúmenes (no hay, pero por las dudas)
```

Entre ensayo y ensayo conviene `restart`, para que app2 vuelva a arrancar en cero y el
efecto "despega desde cero" se vea igual que la primera vez.

---

## 6. Si algo falla

| Síntoma | Causa | Solución |
|---|---|---|
| `docker compose: unknown command` | El plugin no está en el path del CLI | Usar `docker-compose` con guion |
| `bind: address already in use` en 8080 | Otro contenedor ocupa el puerto | `lsof -nP -iTCP:8080 -sTCP:LISTEN`, después `docker rm -f <nombre>` |
| `verificar.sh`: "el proxy no responde" | Los contenedores no terminaron de arrancar | Esperar 5 s y repetir; si sigue, `docker-compose logs nginx` |
| Todos los pedidos dan `401` después de conmutar | `SECRETO` distinto entre app1 y app2 | Tienen que ser idénticos en `docker-compose.yml` |
| Bajo carga el cliente ve muchos errores | El repuesto también satura | `MAX_CONCURRENTES` de app2 debe superar el pico de VUs de k6 (hoy 100 > 60) |
| `X-Estados` nunca muestra dos valores | Falta `http_503` en `proxy_next_upstream` | Es el error más común. Verificar `nginx/nginx.conf` |
| El panel de k6 no abre | k6 < 0.49 | Actualizar, o usar el resumen de texto del final: ya trae p95 y tasa de error |
| Los headers `X-` no aparecen | Falta `always` en los `add_header` | Sin `always` no se agregan en respuestas de error |
| `X-Tiempo-Total` sale `-` en vez de un número | Se usó `$upstream_response_time` | Tiene que ser `$upstream_header_time`: el otro todavía no tiene valor cuando Nginx manda los headers |

**Plan B absoluto:** grabar un video de la demo funcionando la noche anterior. Si algo falla
en vivo, se muestra la grabación y se explica sobre ella.

---

## 7. Mapa de archivos

```
docker-compose.yml   Tres servicios: nginx (8080), app1 (3001), app2 (3002)
nginx/nginx.conf     Reintentos, selección de repuesto y los headers de evidencia
servicio/src/
  index.js           Rutas y latencia simulada de lectura de etiqueta
  auth.js            Autenticar + autorizar (JWT, usuarios en memoria)
  bulkhead.js        Límite de concurrencia: produce la saturación determinista
carga/escenario.js   Escenario de k6 en tres tramos
postman/             Colección con los cinco pedidos de seguridad
verificar.sh         Chequeo automatizado de las cuatro tácticas
plan-demo-tfu.md     Diseño, ADRs, guion de 5 minutos y checklist
```

Hay valores acoplados entre archivos (el límite de app2 contra el pico de k6, el `SECRETO`
entre instancias). Están listados en `CLAUDE.md` antes de tocar ninguno.
