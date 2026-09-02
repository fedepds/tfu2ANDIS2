// Escenario de carga: un vuelo, pico de tres vuelos, vuelve la normalidad.
//
// Se puede correr de dos formas, sin cambiar nada:
//   - k6 instalado en la máquina:   k6 run carga/escenario.js
//   - k6 dentro de Docker:          docker compose --profile carga run --rm --service-ports k6
//
// No hace falta pasar un token: setup() hace el login (operador/1234) una sola vez.
import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://localhost:8080';

// Evidencia agregada que aparece en el resumen final de k6:
//   conmutaciones        respuestas donde Nginx reintentó y conmutó (X-Estados: "503, 200")
//   atendidos_por_app1 / atendidos_por_app2   quién atendió cada pedido con 200
const conmutaciones = new Counter('conmutaciones');
const atendidosPorApp1 = new Counter('atendidos_por_app1');
const atendidosPorApp2 = new Counter('atendidos_por_app2');

export const options = {
  stages: [
    { duration: '15s', target: 5  },   // operación normal: un vuelo
    { duration: '30s', target: 60 },   // pico: tres vuelos simultáneos
    { duration: '15s', target: 5  },   // vuelve la normalidad
  ],
  // Umbrales atados a los criterios de ajuste. k6 los marca con ✓ o ✗ al final.
  thresholds: {
    http_req_duration: ['p(95)<2000'], // CA-1: conmutar en menos de 2 s (el cliente nunca espera más)
    http_req_failed:   ['rate<0.01'],  // disponibilidad: el cliente no ve errores aunque app1 rechace
    checks:            ['rate>0.99'],
  },
};

export function setup() {
  if (__ENV.TOKEN) return { token: __ENV.TOKEN };
  const r = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({ usuario: 'operador', password: '1234' }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  if (r.status !== 200) throw new Error(`login falló contra ${BASE}: ${r.status} ${r.body}`);
  return { token: r.json('token') };
}

export default function (datos) {
  const r = http.get(`${BASE}/api/equipaje/123/scan`, {
    headers: { Authorization: `Bearer ${datos.token}` },
  });
  check(r, { 'equipaje ruteado': (x) => x.status === 200 });

  // "503, 200" en X-Estados = reintento + failover en un solo pedido.
  const estados = r.headers['X-Estados'] || '';
  if (estados.includes(',')) conmutaciones.add(1);

  if (r.status === 200) {
    const instancia = r.json('instancia');
    if (instancia === 'app1') atendidosPorApp1.add(1);
    if (instancia === 'app2') atendidosPorApp2.add(1);
  }
}
