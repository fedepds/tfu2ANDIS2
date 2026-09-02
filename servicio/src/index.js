const express = require('express');
const { login, autenticar, autorizar } = require('./auth');
const { bulkhead, estadisticas } = require('./bulkhead');

const PUERTO = Number(process.env.PUERTO || 3000);
const INSTANCIA = process.env.INSTANCIA || 'sin-nombre';
const LATENCIA_MS = Number(process.env.LATENCIA_MS || 300);

const app = express();
app.disable('x-powered-by');  // el grep '^X-' de la demo debe mostrar solo la evidencia
app.use(express.json());

// --- Rutas públicas -------------------------------------------------------
app.post('/auth/login', login);

app.get('/health', (req, res) => res.json({ instancia: INSTANCIA, estado: 'ok' }));

// Contador por instancia: la evidencia de que app2 no recibe tráfico hasta que
// el primario satura (repuesto redundante en modo warm, ADR-003).
app.get('/stats', (req, res) => res.json(estadisticas()));

// --- Ruteo de equipaje ----------------------------------------------------
// El bulkhead va ANTES de autenticar: una instancia saturada debe responder 503
// sin mirar el token, que es el estímulo que Nginx traduce en reintento + failover.
const api = express.Router();
api.use(bulkhead, autenticar);

// Ruta de carga: la que satura k6. Sólo requiere estar autenticado.
api.get('/equipaje/:id/scan', (req, res) => {
  setTimeout(() => {
    res.json({
      instancia: INSTANCIA,
      equipaje: req.params.id,
      actor: req.actor.usuario,
      destino: 'cinta-3',
    });
  }, LATENCIA_MS); // lectura de la etiqueta
});

// Mismo endpoint, distinto resultado según la identidad: 403 para operador, 200 para
// supervisor. Es la evidencia de que autenticar y autorizar son tácticas distintas.
api.put('/equipaje/:id/ruta', autorizar('supervisor'), (req, res) => {
  res.json({
    instancia: INSTANCIA,
    equipaje: req.params.id,
    rutaNueva: (req.body && req.body.ruta) || 'cinta-7',
    modificadaPor: req.actor.usuario,
  });
});

app.use('/api', api);

app.listen(PUERTO, () => {
  console.log(`[${INSTANCIA}] escuchando en :${PUERTO}`);
});
