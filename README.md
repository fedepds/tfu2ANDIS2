# Demo TFU — Tácticas de Arquitectura

**Grupo 5 · Caso AeroSur · PUC-01 Transportar equipaje**

Banco de pruebas que hace observables cuatro tácticas en vivo:

| Táctica | Dónde vive | Qué se ve |
|---|---|---|
| Reintentos | Nginx | Header `X-Estados: 503, 200` |
| Repuesto redundante (*warm*) | Nginx | `X-Instancias-Probadas` con dos IPs + `/stats` de app2 despegando |
| Autenticar actores | `servicio/src/auth.js` | Sin token → `401` |
| Autorizar actores | `servicio/src/auth.js` | Mismo `PUT`: operador → `403`, supervisor → `200` |

- **Qué decir y en qué orden** (contexto de AeroSur, requerimientos, cierre): `presentacion.md`.
- **Diseño, ADRs y guion cronometrado:** `plan-demo-tfu.md`.
- **Comandos sueltos para copiar y pegar**, con la salida esperada: `COMANDOS.md`.

---

## 0. Requisitos

Para levantar la demo y verificarla **alcanza con Docker**. Todo lo demás es opcional.

| Herramienta | Obligatoria | Para qué |
|---|---|---|
| Docker + Docker Compose | **sí** | Levantar los contenedores; también corre k6 y newman adentro |
| `curl` | no | Los comandos de `COMANDOS.md` y `verificar.sh` (viene con macOS y Linux) |
| Postman | no | Correr la colección con interfaz gráfica |
| `jq` | no | Sólo `verificar.sh` |
| k6 ≥ 0.49 | no | Sólo si se prefiere correr la carga fuera de Docker |

```bash
docker --version && docker compose version
```

> **`docker compose` o `docker-compose`.** En algunas máquinas el plugin (con espacio) no
> está enganchado al CLI y hay que usar el binario con guion. Los scripts detectan cuál hay;
> en los comandos de abajo, si `docker compose` da `unknown command`, usar `docker-compose`.

**Puertos que usa** (todos configurables, ver 1.1): `8080` Nginx, `3001` app1, `3002` app2.
Opcionales: `5665` panel de k6, `3003` Grafana, `9090` Prometheus.

---

## 1. Levantar la demo

```bash
./iniciar.sh
```

Construye las imágenes, levanta los tres contenedores y espera a que el proxy responda. Es lo
mismo que:

```bash
docker compose up --build -d
docker compose ps                     # deben aparecer tres: nginx, app1, app2
```

La primera vez tarda un par de minutos porque construye la imagen del servicio. **Hacelo el
día anterior**, no delante del tribunal: si el día de la exposición no hay red, las imágenes
ya están en caché local y `docker compose up -d` (sin `--build`) levanta igual.

Comprobación rápida:

```bash
curl -s localhost:8080/health    # a través del proxy
curl -s localhost:3001/health    # app1 directo
curl -s localhost:3002/health    # app2 directo
```

### 1.1 Si un puerto está ocupado

Cada puerto del host se puede cambiar con una variable de entorno, sin tocar ningún archivo:

```bash
PUERTO_PROXY=18080 PUERTO_APP1=13001 PUERTO_APP2=13002 ./iniciar.sh
```

| Variable | Servicio | Por defecto |
|---|---|---|
| `PUERTO_PROXY` | Nginx | 8080 |
| `PUERTO_APP1` / `PUERTO_APP2` | instancias (sólo para `/stats`) | 3001 / 3002 |
| `PUERTO_K6` | panel de k6 | 5665 |
| `PUERTO_GRAFANA` / `PUERTO_PROMETHEUS` | observabilidad | 3003 / 9090 |

Las mismas variables las respetan `verificar.sh` y `iniciar.sh`. En Postman, cambiar
`baseUrl`, `app1Url` y `app2Url` en las variables de la colección.

---

## 2. Verificar que las cuatro tácticas funcionan

Tres formas equivalentes. Todas recorren el mismo checklist: los códigos de seguridad, los
tres headers de evidencia y, disparando 20 pedidos en paralelo, que hubo conmutación real al
repuesto y que después el tráfico volvió al primario.

### 2.1 Postman (con interfaz)

Importar `postman/AeroSur-TFU.postman_collection.json` y **Run collection**. Tres carpetas:

| Carpeta | Qué prueba |
|---|---|
| `0 · Salud` | Las tres piezas responden |
| `1 · Seguridad` | Autenticar (401 / 200 + token) y autorizar (403 / 200). Son los cinco pedidos del guion |
| `2 · Disponibilidad` | Estado normal, **pico de 20 pedidos en paralelo desde Postman**, contador de app2, recuperación del primario |

Cada pedido trae sus tests: todo verde = demo lista. El pico lo dispara el pre-request del
pedido 3 con `pm.sendRequest`; la evidencia queda en la consola de Postman. El pedido 5 espera
11 segundos a propósito (el `fail_timeout` de Nginx).

### 2.2 Sin instalar nada: la misma colección con newman dentro de Docker

```bash
docker compose --profile verificacion run --rm newman
```

Corre la colección entera contra los contenedores y sale con error si alguna aserción falla.
Salida esperada al final:

```
│              assertions │                 36 │                 0 │
```

### 2.3 Con `curl`

- Pedido por pedido, para mostrar en vivo o para que lo prueben los profesores: `COMANDOS.md`.
- Todo junto: `./verificar.sh` (necesita `jq`).

```
Tácticas de disponibilidad (reintentos / repuesto redundante)
  OK   hubo conmutación: X-Estados: 503, 200
  OK   X-Instancias-Probadas: 172.18.0.3:3000, 172.18.0.2:3000
  OK   app2 atendió pedidos por primera vez (0 -> 15)

Todo verde. La demo está lista.
```

> Después de cualquier verificación, app1 queda marcada como caída por Nginx durante 10
> segundos. Esperá ese rato antes de empezar la exposición para que el primer pedido del
> guion salga del primario. Para dejar los contadores en cero sin reiniciar nada:
>
> ```bash
> curl -s -X POST localhost:3001/stats/reset; curl -s -X POST localhost:3002/stats/reset
> ```

---

## 3. Tácticas de seguridad (Postman)

Carpeta `1 · Seguridad`. Los cinco pedidos van en orden y los logins guardan el token solos en
la variable de colección — **no hay que copiar y pegar nada en vivo**.

| # | Pedido | Esperado | Táctica |
|---|---|---|---|
| 1 | `PUT /api/equipaje/123/ruta` sin token | `401 falta token` | Autenticar |
| 2 | `POST /auth/login` con `operador/1234` | `200` + token | Autenticar |
| 3 | `PUT` con token de **operador** | `403 rol sin permiso` | Autorizar |
| 4 | `POST /auth/login` con `supervisor/1234` | `200` + token | — |
| 5 | `PUT` con token de **supervisor** | `200 ruta modificada` | Autorizar |

**Lo que hay que decir en el 3 y el 5:** mismo endpoint, mismo sistema, distinta identidad.
Ahí se ve que autenticar y autorizar son dos tácticas distintas.

Usuarios disponibles: `operador/1234` y `supervisor/1234`. (El pedido `2b`, login con password
incorrecta, está en la colección para la verificación; en vivo se puede saltar.)

---

## 4. Tácticas de disponibilidad

### 4.1 Los headers en operación normal

```bash
TOKEN=$(curl -s -X POST localhost:8080/auth/login -H 'Content-Type: application/json' -d '{"usuario":"operador","password":"1234"}' | jq -r .token)
curl -si localhost:8080/api/equipaje/1/scan -H "Authorization: Bearer $TOKEN" | grep '^X-'
```

Con poca carga aparece **una sola IP** y **un solo estado**: todo lo atiende el primario.

```
X-Instancias-Probadas: 172.18.0.3:3000
X-Estados: 200
X-Tiempo-Total: 0.307
```

### 4.2 La ventana de contadores

En una terminal aparte, dejar corriendo:

```bash
while true; do clear; curl -s localhost:3001/stats; echo; curl -s localhost:3002/stats; echo; sleep 1; done
```

`atendidos` de **app2 tiene que estar en cero** antes de arrancar el pico. Ese cero es la
evidencia de que el repuesto está *warm*: encendido pero sin tráfico.

### 4.3 El pico corto (20 pedidos, un comando)

Para la exposición alcanza con esto; es lo que hace el pedido 3 de Postman:

```bash
curl -sZ --parallel-max 20 -o /dev/null -D - -H "Authorization: Bearer $TOKEN" "localhost:8080/api/equipaje/[1-20]/scan" | grep -i '^X-' | grep -B1 -A1 ', 200' | head -3
```

```
X-Instancias-Probadas: 172.18.0.3:3000, 172.18.0.2:3000
X-Estados: 503, 200
X-Tiempo-Total: 0.002, 0.305
```

Esas tres líneas son el reintento **y** el failover al repuesto **y** el tiempo que tardó la
conmutación, en una sola respuesta.

### 4.4 El pico largo (k6, 60 segundos)

Sin instalar k6: corre dentro de Docker y hace el login solo.

```bash
docker compose --profile carga run --rm --service-ports k6
```

Panel en **http://localhost:5665** mientras corre. Con k6 instalado es lo mismo:

```bash
K6_WEB_DASHBOARD=true k6 run carga/escenario.js
```

Tres tramos:

| Tramo | VUs | Qué pasa |
|---|---|---|
| 0–15 s | 5 | Operación normal: un vuelo. Todo lo atiende app1 |
| 15–45 s | 60 | Pico de tres vuelos. app1 satura y empiezan los 503 → conmutación |
| 45–60 s | 5 | Vuelve la normalidad. El tráfico regresa solo al primario |

**Qué señalar mientras corre:** la tasa de error del primario subiendo, el contador de **app2
despegando desde cero**, y los headers de una respuesta cualquiera desde otra terminal (4.3).

### 4.5 Cerrar con los criterios de ajuste

Al terminar, k6 imprime el resumen con los umbrales atados a los criterios:

```
✓ http_req_duration: 'p(95)<2000'  p(95)=309.73ms    CA-1: conmutar en menos de 2 s
✓ http_req_failed:   'rate<0.01'   rate=0.00%        el cliente nunca vio un error
  atendidos_por_app1...: 164
  atendidos_por_app2...: 4756                        lo que absorbió el repuesto
  conmutaciones........: 18                          respuestas con "503, 200"
```

- **CA-2 pide tres reintentos.** En pantalla: `proxy_next_upstream_tries 3` en `nginx.conf`.
- **CA-1 pide conmutar en menos de 2 s.** En pantalla: el `p(95)` del resumen (del orden de
  **300 ms**) y el segundo valor de `X-Tiempo-Total`.

Una corrida sana termina con `http_req_failed: 0.00%`: el cliente **nunca vio un error**, aunque
el primario haya rechazado pedidos. Eso *es* la disponibilidad.

---

## 5. Opcional: ver la conmutación en un gráfico (Grafana)

Para que se vea *visualmente* cómo el tráfico pasa de un contenedor al otro. Es un perfil
aparte: **no se levanta salvo que se pida**, y la demo no depende de él.

```bash
docker compose --profile observabilidad up -d
```

Abre **http://localhost:3003** directo en el tablero *AeroSur · conmutación app1 → app2*, sin
login. Prometheus raspa `/metrics` de cada instancia una vez por segundo; el tablero se
refresca cada segundo y muestra:

- **Pedidos atendidos por segundo, por instancia:** app1 en azul, app2 en naranja. Durante el
  pico la curva naranja despega desde cero y al bajar la carga vuelve a cero.
- **Rechazos (503) por segundo:** el primario saturado.
- Contadores de atendidos, en vuelo y rechazados.

Correr el k6 de 4.4 con el tablero abierto es la versión visual de toda la sección 4.

Para apagarlo junto con lo demás: `docker compose --profile observabilidad down`.

---

## 6. Apagar y reiniciar

```bash
curl -s -X POST localhost:3001/stats/reset; curl -s -X POST localhost:3002/stats/reset   # contadores a cero
docker compose down                # apaga y borra los contenedores
docker compose --profile observabilidad --profile carga --profile verificacion down   # todo, incluidos los perfiles
```

Entre ensayo y ensayo conviene el `reset`, para que app2 vuelva a cero y el efecto "despega
desde cero" se vea igual que la primera vez. Es preferible a reiniciar contenedores: al
reiniciar app1 y app2 sueltas pueden intercambiar IPs; Nginx ahora vuelve a resolver los
nombres cada 2 s (`resolve` en `nginx.conf`) justamente para tolerar eso, pero el reset no
toca nada y es instantáneo.

---

## 7. Si algo falla

| Síntoma | Causa | Solución |
|---|---|---|
| `docker compose: unknown command` | El plugin no está en el path del CLI | Usar `docker-compose` con guion |
| `bind: address already in use` | Otro contenedor ocupa el puerto | `PUERTO_PROXY=18080 ./iniciar.sh` (ver 1.1), o `lsof -nP -iTCP:8080 -sTCP:LISTEN` y `docker rm -f <nombre>` |
| `iniciar.sh`: "el proxy no respondió" | Los contenedores no terminaron de arrancar | Esperar 5 s y repetir; si sigue, `docker compose logs nginx` |
| Todos los pedidos dan `401` después de conmutar | `SECRETO` distinto entre app1 y app2 | Tienen que ser idénticos en `docker-compose.yml` |
| Bajo carga el cliente ve muchos errores | El repuesto también satura | `MAX_CONCURRENTES` de app2 debe superar el pico de VUs de k6 (hoy 100 > 60) |
| `X-Estados` nunca muestra dos valores | Falta `http_503` en `proxy_next_upstream` | Es el error más común. Verificar `nginx/nginx.conf` |
| Los headers `X-` no aparecen | Falta `always` en los `add_header` | Sin `always` no se agregan en respuestas de error |
| `X-Tiempo-Total` sale `-` en vez de un número | Se usó `$upstream_response_time` | Tiene que ser `$upstream_header_time` |
| Después de reiniciar app1/app2, todo lo atiende app2 y nunca conmuta | Las instancias intercambiaron IP y Nginx se quedó con la resolución vieja | Ya no debería pasar: `nginx.conf` usa `resolve` y re-resuelve cada 2 s. Si pasa, `docker compose restart nginx` |
| Postman: el pedido 3 de Disponibilidad no muestra conmutación | Se corrió sin token o app2 estaba saturada | Correr la colección entera; ver que `pico` (20) sea menor que `MAX_CONCURRENTES` de app2 |
| Postman: el pedido 5 falla ("lo atendió app2") | No pasaron 10 s desde el pico | Subir `esperaRecuperacionMs` en las variables de la colección |
| `curl: option -Z: is unknown` | curl anterior a 7.66 | Usar el bucle `for` de `COMANDOS.md` §4 |
| El panel de k6 no abre | k6 < 0.49 fuera de Docker | Usar el perfil `carga` de Docker, o el resumen de texto del final |
| Grafana muestra "No data" | Prometheus todavía no raspó | Esperar 5 s; verificar `localhost:9090/targets` con los dos *up* |
| k6 termina con muchos errores de golpe | Se corrió `iniciar.sh` o `up --build` **durante** la carga y recreó app1/app2 | No tocar los contenedores con la demo andando. El proxy se recupera solo en ~3 s, pero a 60 VUs eso son miles de 503 |

**Plan B absoluto:** grabar un video de la demo funcionando la noche anterior. Si algo falla
en vivo, se muestra la grabación y se explica sobre ella.

---

## 8. Mapa de archivos

```
iniciar.sh            Levanta la demo y espera a que responda (PUERTO_*, PERFIL=observabilidad)
verificar.sh          Chequeo de las cuatro tácticas con curl + jq
COMANDOS.md           Los mismos chequeos como comandos sueltos, con salida esperada
presentacion.md       Guion: contexto de AeroSur, requerimientos, qué decir, cierre, preguntas
plan-demo-tfu.md      Diseño, ADRs, guion cronometrado y checklist
docker-compose.yml    nginx (8080), app1 (3001), app2 (3002) + perfiles carga / verificacion / observabilidad
nginx/nginx.conf      Reintentos, selección de repuesto, re-resolución DNS y los headers de evidencia
servicio/src/
  index.js            Rutas, latencia simulada, /stats, /stats/reset y /metrics
  auth.js             Autenticar + autorizar (JWT, usuarios en memoria)
  bulkhead.js         Límite de concurrencia: produce la saturación determinista
carga/escenario.js    Escenario de k6 en tres tramos; hace el login solo; umbrales = criterios
postman/
  AeroSur-TFU.postman_collection.json   Salud + seguridad + disponibilidad (reemplaza al script)
  generar_coleccion.py                  Genera el JSON; editar acá, no el JSON a mano
observabilidad/       prometheus.yml y el tablero de Grafana provisionado
```

## 9. Valores acoplados entre archivos

Antes de tocar uno, mover el otro:

| Valor | Dónde | Acoplado con |
|---|---|---|
| `MAX_CONCURRENTES` de app2 (100) | `docker-compose.yml` | Pico de k6 (60 VUs) y `pico` de Postman (20): tienen que quedar por debajo |
| `SECRETO` | `docker-compose.yml`, ambas instancias | Si difieren, el failover da 401 |
| `fail_timeout=10s` | `nginx/nginx.conf` | `esperaRecuperacionMs` (11000) en la colección de Postman y el `sleep 11` de `COMANDOS.md` |
| `max_fails=2` | `nginx/nginx.conf` | Con `pico` de 20 se alcanza seguro; con menos de 7 podría no marcarse caído app1 |
| `http_503` en `proxy_next_upstream` | `nginx/nginx.conf` | El 503 de `bulkhead.js`: sin uno el otro no sirve |
| Nombres de host `nginx`, `app1`, `app2` | `docker-compose.yml` | `nginx.conf`, `prometheus.yml`, y los `--env-var` del servicio `newman` |
