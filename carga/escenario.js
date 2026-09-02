import http from 'k6/http';
import { check } from 'k6';

const TOKEN = __ENV.TOKEN;

export const options = {
  stages: [
    { duration: '15s', target: 5  },   // operación normal: un vuelo
    { duration: '30s', target: 60 },   // pico: tres vuelos simultáneos
    { duration: '15s', target: 5  },   // vuelve la normalidad
  ],
};

export default function () {
  const r = http.get('http://localhost:8080/api/equipaje/123/scan', {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  check(r, { 'equipaje ruteado': (x) => x.status === 200 });
}
  