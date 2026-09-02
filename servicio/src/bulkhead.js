// Andamiaje de la demo, NO una de las cuatro tácticas demostradas (ver ADR-002).
//
// Límite explícito de trabajo concurrente. Es en sí mismo una táctica de rendimiento
// (limitar el tamaño de las colas / patrón Bulkhead), pero acá se usa como instrumento
// para producir el estímulo del escenario de disponibilidad de forma determinista:
// la saturación del primario no depende del hardware del expositor.
//
// Con LATENCIA_MS=300 y MAX_CONCURRENTES=5 la capacidad de app1 es de ~16 pedidos/s.
// Cualquier carga por encima produce 503 inmediatos y reproducibles.
const MAX_CONCURRENTES = Number(process.env.MAX_CONCURRENTES || 5);
const INSTANCIA = process.env.INSTANCIA || 'sin-nombre';

let enVuelo = 0;
let atendidos = 0;
let rechazados = 0;

function bulkhead(req, res, next) {
  if (enVuelo >= MAX_CONCURRENTES) {
    rechazados++;
    return res.status(503).json({ instancia: INSTANCIA, error: 'servicio saturado' });
  }
  enVuelo++;
  atendidos++;
  // 'close' y no 'finish': bajo el pico k6 aborta conexiones y 'finish' no siempre
  // dispara. Si el contador no baja, app1 queda saturada para siempre y nunca se ve
  // el tramo de recuperación del guion.
  res.on('close', () => { enVuelo--; });
  next();
}

function estadisticas() {
  return { instancia: INSTANCIA, maxConcurrentes: MAX_CONCURRENTES, enVuelo, atendidos, rechazados };
}

// Vuelve los contadores a cero SIN reiniciar el contenedor. Reiniciar app1/app2 sueltas
// es peligroso: pueden intercambiar IPs y Nginx, que resolvió los nombres al arrancar,
// queda mandando el tráfico "de app1" a app2. Verificado en banco.
function reiniciarContadores() {
  atendidos = 0;
  rechazados = 0;
  return estadisticas();
}

// Los mismos contadores en formato de texto de Prometheus, para el perfil de
// observabilidad (Grafana). Sin librerías: son cuatro líneas por métrica.
function metricas() {
  const etiqueta = `instancia="${INSTANCIA}"`;
  return [
    '# HELP equipaje_pedidos_atendidos_total Pedidos que la instancia aceptó procesar.',
    '# TYPE equipaje_pedidos_atendidos_total counter',
    `equipaje_pedidos_atendidos_total{${etiqueta}} ${atendidos}`,
    '# HELP equipaje_pedidos_rechazados_total Pedidos rechazados con 503 por saturación.',
    '# TYPE equipaje_pedidos_rechazados_total counter',
    `equipaje_pedidos_rechazados_total{${etiqueta}} ${rechazados}`,
    '# HELP equipaje_pedidos_en_vuelo Pedidos en curso en este instante.',
    '# TYPE equipaje_pedidos_en_vuelo gauge',
    `equipaje_pedidos_en_vuelo{${etiqueta}} ${enVuelo}`,
    '# HELP equipaje_max_concurrentes Límite de concurrencia configurado (MAX_CONCURRENTES).',
    '# TYPE equipaje_max_concurrentes gauge',
    `equipaje_max_concurrentes{${etiqueta}} ${MAX_CONCURRENTES}`,
    '',
  ].join('\n');
}

module.exports = { bulkhead, estadisticas, metricas, reiniciarContadores };
