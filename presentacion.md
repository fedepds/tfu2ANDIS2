# Guion de la presentación — TFU UT2

**Grupo 5 · Caso AeroSur · PUC-01 Transportar equipaje**
**Duración máxima:** 5 minutos (grabación). El mismo guion sirve si nos sortean para presentar en clase.

Este documento es lo que se dice, en qué orden y por qué. El **cómo** correr cada cosa está en
`README.md` y `COMANDOS.md`; el diseño y los ADRs, en `plan-demo-tfu.md`.

La estructura sigue el orden que evalúa la cátedra: **contexto → requerimiento → táctica →
evidencia → comparación con el criterio de ajuste**. Si se recorta algo por tiempo, se recorta la
demo (hay video de respaldo), nunca el contexto ni el cierre.

---

## Minuto a minuto

| Tiempo | Bloque | Pantalla |
|---|---|---|
| 0:00–0:40 | 1. Contexto de la empresa y del caso de uso | Diapositiva 1 |
| 0:40–1:20 | 2. Los requerimientos no funcionales | Diapositiva 2 |
| 1:20–1:50 | 3. Tácticas elegidas y dónde vive cada una | Diapositiva 3 (diagrama) |
| 1:50–2:40 | 4. Demo de seguridad | Postman, carpeta 1 |
| 2:40–4:15 | 5. Demo de disponibilidad | Postman carpeta 2 / k6 / Grafana |
| 4:15–4:45 | 6. Cierre: criterios de ajuste vs. números medidos | Diapositiva 4 |
| 4:45–5:00 | 7. Simplificaciones declaradas | Diapositiva 5 |

---

## 1. Contexto de la empresa y del caso de uso (0:00–0:40)

Esto es lo que faltaba en las presentaciones anteriores: **antes de mostrar nada, decir para
quién es el sistema y por qué importa el requerimiento.** Sin contexto, la demo parece una
exhibición de herramientas.

**Qué decir:**

> AeroSur es una aerolínea regional con base en Montevideo. En los últimos años digitalizó la
> venta, el check-in y la gestión de pasajeros; hoy tiene una App Móvil, una API central y
> servicios de Reservas, Check-in, Equipaje, Millas, Notificaciones y una pasarela de pagos.
>
> Está por entrar en una etapa de expansión. Dos puntos de esa expansión son los que nos
> importan: incorpora **cintas automatizadas para transportar equipaje**, con sensores y
> escáneres, y necesita **reforzar el control sobre las operaciones administrativas que
> modifican información crítica**.
>
> Nosotros trabajamos sobre el **Servicio de Equipaje** y el caso de uso **PUC-01, Transportar
> equipaje**: un escáner lee la etiqueta de cada valija, el servicio decide a qué cinta va, y un
> supervisor puede cambiar esa ruta, por ejemplo si cambió el vuelo.

**Por qué importa (una frase cada uno):**

- Si el servicio de ruteo no responde, la cinta se detiene: valijas que no llegan al vuelo, y en
  un pico de tres vuelos simultáneos eso son cientos de pasajeros. De ahí **disponibilidad**.
- Si cualquiera puede cambiar la ruta de una valija, el equipaje se pierde o se manda a otro
  destino. De ahí **seguridad**: saber quién pide y qué tiene permitido.

---

## 2. Los requerimientos no funcionales (0:40–1:20)

**Qué es un requerimiento no funcional, en veinte segundos** (por si el tribunal lo pide o el
público no es de la materia):

> Un requerimiento funcional dice *qué* hace el sistema: "rutea la valija a una cinta". Un
> requerimiento no funcional dice *qué tan bien* tiene que hacerlo: en cuánto tiempo, con qué
> disponibilidad, quién puede. Cada uno se ata a un **atributo de calidad** y trae un **criterio
> de ajuste**: un número o una condición verificable, que es lo que la demo tiene que probar.

**Los dos requerimientos de la Parte 1** (texto del documento entregado; leerlo, no improvisar):

| Campo | RNF-DIS-01 · Disponibilidad | RNF-SEG-01 · Seguridad |
|---|---|---|
| Caso de uso | PUC-01 – Transportar equipaje | PUC-01 – Transportar equipaje |
| Descripción | El sistema deberá mantener disponible el procesamiento del ruteo de equipaje, ejecutando **reintentos** automáticos ante fallas transitorias de red al leer las etiquetas del equipaje, y redirigiendo el tráfico a servidores secundarios mediante **replicación** si el sistema principal de procesamiento falla. | El sistema deberá **autenticar** a los actores y **autorizar** a los actores para garantizar que solo personal verificado con el rol correcto manipule el ruteo del equipaje. |
| Justificación | Una interrupción en el sistema de transporte y escaneo de equipaje provocaría retrasos operativos masivos en los vuelos de AeroSur y pérdida del ruteo de las maletas. | Contener estados inseguros evitando interacciones ilegítimas. *(ver ajuste sugerido abajo)* |
| Criterio de ajuste | **CA-1:** al simular la caída del servidor principal, el sistema debe redirigir el procesamiento a la réplica en **menos de 2 segundos**. **CA-2:** ante la pérdida de red transitoria de un escáner, el sistema debe reintentar la conexión **3 veces** antes de notificar un error. | El sistema bloqueará **de inmediato** cualquier intento de acceso que falle la autenticación de identidad o la autorización del rol. |
| Prioridad | Must have | Must have |
| Conflictos | Aumento en los costos por mantener servidores de réplica encendidos. | No existen |

**Cómo se conectan con el contexto de AeroSur (decirlo con estas palabras):**

- RNF-DIS-01: los escáneres están sobre la cinta, con red que se corta y firmware difícil de
  actualizar; no pueden ser ellos los que manejen la falla. Y un pico de tres vuelos satura una
  instancia; parar la cinta no es opción. El **conflicto** declarado (réplica encendida = costo)
  es lo que justifica elegir un repuesto *warm* y no *hot* (ADR-003).
- RNF-SEG-01: AeroSur pide reforzar el control sobre las operaciones que modifican información
  crítica. Un operador consulta; sólo un supervisor cambia rutas. Autenticado no significa
  autorizado.

**Cómo dijimos en la Parte 1 que las tácticas lo satisfacen** (resumen fiel del documento):

- *Reintentar* aborda fallas transitorias (un microcorte de red, una demora): se vuelve a
  ejecutar la operación esperando que el próximo intento sea exitoso. Cubre la parte del
  requerimiento que pide reintentar.
- *Repuesto redundante* mantiene una alternativa capaz de asumir el servicio ante la falla de
  otro componente (hot, warm o cold). Si una instancia deja de responder, otra continúa
  procesando. Entre las dos, el ruteo se mantiene disponible.
- *Autenticar actores* es la primera línea de defensa: validar usuario y contraseña evita
  accesos no identificados.
- *Autorizar actores*: superada la autenticación, el rol define a qué se tiene acceso. Si un
  operador intenta una función reservada al supervisor, el sistema intercepta el pedido y lo
  deniega.

> **Ajustes sugeridos a la Parte 1 antes de entregar** (son cambios de redacción, no de fondo):
>
> 1. **Justificación de RNF-SEG-01.** "Contener estados inseguros" es vocabulario de la
>    categoría *protección* (safety), no de *seguridad*. Mejor atarla al caso: *"AeroSur necesita
>    reforzar el control sobre las operaciones administrativas que modifican información crítica;
>    una modificación de ruta hecha por alguien no identificado o sin el rol adecuado manda
>    equipaje al destino equivocado."*
> 2. **Criterio de ajuste de RNF-SEG-01.** "De inmediato" no es medible. Versión verificable,
>    que es exactamente lo que la demo muestra: *"Todo pedido sin credencial válida se rechaza
>    con 401 sin ejecutar la operación; todo pedido de un actor autenticado cuyo rol no tiene
>    permiso se rechaza con 403 sin ejecutar la operación."*
> 3. **Nombre de la táctica.** La descripción de RNF-DIS-01 dice "mediante replicación"; el
>    catálogo llama *repuesto redundante* a lo que recupera el servicio. Escribir "mediante una
>    réplica mantenida como repuesto redundante" deja las dos palabras.
> 4. **Atomicidad (opcional).** Los dos requerimientos unen dos capacidades con "y" y tienen
>    (o deberían tener) dos criterios. Si el docente lo marca, se parten en RNF-DIS-01/02 y
>    RNF-SEG-01/02 sin cambiar el contenido (sección 10 de `plan-demo-tfu.md`).

---

## 3. Tácticas elegidas y dónde vive cada una (1:20–1:50)

**La combinación de la consigna** que elegimos: *replicación y re-intentos para disponibilidad,
y dos tácticas de la categoría resistir a ataques para seguridad.*

**Qué decir sobre el diagrama:**

> Cuatro tácticas, en dos elementos distintos. Las dos de disponibilidad viven en el **proxy
> inverso**, porque es el elemento que *detecta* la falla, no el que la sufre: **reintentos**
> y **repuesto redundante**. La réplica es una segunda instancia idéntica, encendida y con
> estado inicializado, que no recibe tráfico mientras el primario responda: un repuesto
> *warm*. Las dos de seguridad viven en la **aplicación**, en un middleware que corre antes de
> cada operación: **autenticar actores** y **autorizar actores**.

**Nomenclatura del catálogo, para no perder puntos:** la consigna dice "replicación"; en el
catálogo de la materia, lo que se aplica para *recuperarse* de la falla se llama **repuesto
redundante** (*replicación* aparece bajo *voto*, en *detectar fallas*). Decir las dos cosas:
"replicamos la instancia y la usamos como repuesto redundante".

| Táctica | Categoría | Dónde vive | Mecanismo concreto |
|---|---|---|---|
| Reintentos | Disponibilidad · recuperarse de fallas | Nginx | `proxy_next_upstream ... http_503`, `proxy_next_upstream_tries 3` |
| Repuesto redundante (warm) | Disponibilidad · recuperarse de fallas | Nginx | `server app2 backup` en el *upstream* |
| Autenticar actores | Seguridad · resistir ataques | `servicio/src/auth.js` | Login que emite un JWT firmado; verificación del token en cada pedido |
| Autorizar actores | Seguridad · resistir ataques | `servicio/src/auth.js` | Middleware que compara el *claim* `rol` con los roles permitidos del endpoint |

**Decirlo antes de que lo pregunten:** la saturación del primario la provocamos con un límite de
concurrencia explícito (*bulkhead*). Eso **no** es una de las cuatro tácticas: es el andamiaje
que hace la falla reproducible en cualquier máquina (ADR-002). Mostrar que se entiende la
diferencia entre la táctica y el instrumento vale más que esconderlo.

---

## 4. Demo de seguridad (1:50–2:40)

Postman, carpeta **1 · Seguridad**, los cinco pedidos en orden. Los logins guardan el token
solos; no se copia nada en vivo.

| Pedido | Resultado | Qué se dice |
|---|---|---|
| 1 · PUT ruta sin token | `401` | "Sin credencial no hay conversación. Ni llega a la lógica de ruteo. Autenticar." |
| 2 · Login operador | `200` + token | "El operador se identifica y recibe una credencial firmada." |
| 3 · PUT ruta con token de operador | `403` | "Está autenticado, sabemos quién es. Pero su rol no puede cambiar rutas. Autorizar." |
| 4 · Login supervisor | `200` + token | (sin comentario, es un paso técnico) |
| 5 · PUT ruta con token de supervisor | `200` | "**Mismo endpoint, mismo sistema, distinta identidad.** Ahí se ve que son dos tácticas distintas." |

La frase del pedido 5 es la que hay que decir con calma mirando a cámara. Es el punto fuerte.

---

## 5. Demo de disponibilidad (2:40–4:15)

Ventanas preparadas de antemano: Postman (carpeta **2 · Disponibilidad**), una terminal y, si
se usa, Grafana en el navegador. Zoom de la terminal alto.

**5.1 Estado normal (20 s).** Pedido 2 de la carpeta, o en la terminal:

```
X-Instancias-Probadas: 172.18.0.3:3000
X-Estados: 200
X-Tiempo-Total: 0.306
```

> "Estos tres headers los agrega el proxy y son nuestra evidencia. En operación normal hay
> una sola instancia y un solo estado: todo lo atiende el primario. Y el contador de app2 está
> en cero: el repuesto está encendido pero sin tráfico."

**5.2 El pico (40 s).** Pedido 3 de la carpeta (20 pedidos en paralelo) o el `curl --parallel`
de `COMANDOS.md`. Señalar la respuesta que muestra:

```
X-Instancias-Probadas: 172.18.0.3:3000, 172.18.0.2:3000
X-Estados: 503, 200
X-Tiempo-Total: 0.002, 0.305
```

> "Una sola respuesta y están las dos tácticas. El primario rechazó con 503, el proxy
> **reintentó** contra el **repuesto**, y el cliente recibió 200. El escáner nunca se enteró.
> Y el tiempo: 2 milisegundos en detectar la falla, 305 en responder desde el repuesto."

Si hay Grafana (opcional, sólo si se ensayó): mientras corre k6, la curva de app2 **despega
desde cero** y los rechazos de app1 suben. Es la misma evidencia, en un gráfico. No detenerse
a explicar Grafana: es un termómetro, no la táctica.

**5.3 Recuperación (20 s).** Pedido 5 de la carpeta, o esperar 11 s y repetir el pedido normal:

> "Vencido el `fail_timeout` de diez segundos, el proxy vuelve a probar el primario y el
> tráfico regresa solo. No hay intervención manual."

Si el tiempo aprieta, **este es el tramo que se recorta**.

---

## 6. Cierre: criterios de ajuste vs. números medidos (4:15–4:45)

**Esto decide la nota.** No cerrar con "funciona"; cerrar comparando cada criterio con lo que se
vio en pantalla.

| Criterio de ajuste | Dónde está el número |
|---|---|
| RNF-DIS-01 · CA-2 · reintenta **3 veces** antes de notificar error | `proxy_next_upstream_tries 3` en `nginx.conf`; en la demo alcanzó con un reintento porque el repuesto respondió |
| RNF-DIS-01 · CA-1 · redirige a la réplica en **menos de 2 s** | `X-Tiempo-Total: 0.002, 0.305`; p(95) de k6 del orden de 300 ms; umbral `p(95)<2000` en verde |
| RNF-SEG-01 · bloquea **de inmediato** lo que falla la autenticación | Pedido 1 de Postman: sin token → **401**, la operación no se ejecuta |
| RNF-SEG-01 · bloquea **de inmediato** lo que falla la autorización del rol | Pedido 3 de Postman: operador → **403**, la operación no se ejecuta |

> "Los criterios que escribimos en la Parte 1 tienen un número o un código medido en esta demo.
> Y un dato más: bajo el pico, k6 reporta 0 % de errores del lado del cliente aunque el
> primario haya rechazado cientos de pedidos. **Eso es la disponibilidad.**"

---

## 7. Simplificaciones declaradas (4:45–5:00)

Decirlas antes de que las pregunten. Muestra criterio, no debilidad.

- **Usuarios en memoria**, sin base de datos: la táctica que se demuestra es la verificación
  de identidad, no su almacenamiento.
- **La falla es simulada** con un límite de concurrencia (ADR-002). Un servidor real degrada
  gradualmente; acá rechaza limpio para que la demo sea reproducible.
- **El proxy es punto único de falla** (ADR-001). En producción se replica con IP virtual o
  *keepalived*; acá se asume disponible.
- **Repuesto warm, no hot** (ADR-003): un repuesto caliente aprovecharía mejor los recursos
  pero haría invisible el failover, que es lo que hay que mostrar.

---

## 8. Preguntas probables y respuestas preparadas

| Pregunta | Respuesta |
|---|---|
| ¿Por qué los reintentos en Nginx y no en la app o el cliente? | Las tácticas de recuperación se aplican en el elemento que *detecta* la falla. El cliente son escáneres con firmware difícil de actualizar; la app que satura no puede reintentarse a sí misma. ADR-001. |
| ¿Por qué no un *circuit breaker*? | Es el patrón que complementa a reintentos cuando la falla deja de ser transitoria. Queda fuera porque la combinación de tácticas venía dada por la consigna; lo nombramos como siguiente paso. |
| ¿Qué pasa si el repuesto también satura? | Pasa exactamente lo que evitamos: el cliente ve errores. Por eso `MAX_CONCURRENTES` de app2 (100) es mayor que el pico (60 VUs). Lo verificamos: con 50 falla el 97 % de los pedidos. |
| ¿Esto es microservicios? | No. Es estilo basado en servicios: dos instancias replicadas de *un* servicio detrás de un intermediario. No hay un impulsor que pida descomposición funcional, sólo redundancia. |
| ¿El *bulkhead* no es una táctica? | Sí, de rendimiento (limitar el tamaño de las colas). Acá es andamiaje para producir el estímulo; no la contamos entre las cuatro. |
| ¿Replicación o repuesto redundante? | Replicamos la instancia y la usamos como repuesto redundante en modo *warm*. En el catálogo, *replicación* aparece bajo *voto* (detectar); lo que recupera es *repuesto redundante*. |
| ¿Cómo se autenticaría un escáner real? | Con una credencial de dispositivo (certificado o token de larga duración) en vez de usuario y contraseña. La táctica es la misma: verificar la identidad antes de operar. |
| ¿Qué pasa si cae Nginx? | Se cae todo: es el punto único de falla declarado. Se resuelve replicando el proxy (IP virtual / keepalived), fuera del alcance de la demo. |
| ¿Por qué JWT con secreto compartido? | Simplificación: las dos instancias deben poder verificar el mismo token, si no el failover daría 401. En producción, clave asimétrica o un emisor central. |

---

## 9. Puntos de mejora que aplica este guion

Lo que se marcó como mejora en las presentaciones anteriores, y dónde queda cubierto acá:

| Punto de mejora | Cómo se aplica |
|---|---|
| Dar contexto de la empresa antes de la demo | Bloque 1 completo, 40 segundos, con el texto del caso |
| Explicar el requerimiento antes de mostrar la táctica | Bloque 2: qué es un RNF y lectura textual de RNF-DIS-01 y RNF-SEG-01 |
| Nombrar las tácticas con el nombre del catálogo | Tabla del bloque 3 y aclaración replicación / repuesto redundante |
| Que los números apunten al criterio de ajuste | Bloque 6: una fila por criterio con el número medido |
| Declarar las simplificaciones en vez de que las descubran | Bloque 7 y ADRs |
| Cumplir el tiempo | Minuto a minuto arriba; el tramo recortable es 5.3 |
| Que se lea desde el fondo del aula | Zoom de terminal, tres headers, no logs |

---

## 10. Estructura de la grabación

Cinco diapositivas y la demo. Nada de texto corrido: títulos, una tabla, un diagrama.

1. **Portada + contexto:** AeroSur, expansión, PUC-01. Una foto de una cinta de equipaje ayuda.
2. **Los requerimientos:** la tabla del bloque 2 (RNF-DIS-01 y RNF-SEG-01, criterios en negrita).
3. **Arquitectura:** el diagrama de `plan-demo-tfu.md` (k6 / Postman → Nginx → app1, app2).
   Con las cuatro tácticas ubicadas sobre el elemento donde viven.
4. **Cierre:** tabla criterio ↔ número medido (bloque 6).
5. **Simplificaciones y próximos pasos:** bloque 7 más *circuit breaker* y réplica del proxy.

La demo va entre la 3 y la 4, grabada en pantalla. Grabar dos tomas y quedarse con la que
entra en 5:00.

**Antes de grabar:**

- `./iniciar.sh` la noche anterior, imágenes ya en caché.
- `docker compose --profile verificacion run --rm newman`: todo verde.
- `curl -X POST localhost:3001/stats/reset` y lo mismo en `3002`, para que app2 arranque en cero.
- Esperar 10 s después de cualquier prueba antes de grabar el estado normal.
- Video de respaldo grabado por si algo falla en vivo.
