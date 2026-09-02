#!/usr/bin/env python3
"""Genera AeroSur-TFU.postman_collection.json.

La colección se edita acá (Python) y no a mano en el JSON: los scripts de Postman quedan
legibles como código y el JSON se regenera con `python3 postman/generar_coleccion.py`.
"""
import json
import pathlib

SALIDA = pathlib.Path(__file__).with_name('AeroSur-TFU.postman_collection.json')


def lineas(codigo):
    return [l for l in codigo.strip('\n').split('\n')]


def url(base_var, ruta):
    return {
        'raw': '{{%s}}%s' % (base_var, ruta),
        'host': ['{{%s}}' % base_var],
        'path': [p for p in ruta.strip('/').split('/')],
    }


def pedido(nombre, metodo, ruta, base='baseUrl', cuerpo=None, token=False, tests=None, pre=None, descripcion=None):
    headers = []
    if cuerpo is not None:
        headers.append({'key': 'Content-Type', 'value': 'application/json'})
    if token:
        headers.append({'key': 'Authorization', 'value': 'Bearer {{token}}'})
    item = {
        'name': nombre,
        'request': {'method': metodo, 'header': headers, 'url': url(base, ruta)},
    }
    if descripcion:
        item['request']['description'] = descripcion
    if cuerpo is not None:
        item['request']['body'] = {'mode': 'raw', 'raw': json.dumps(cuerpo, ensure_ascii=False)}
    eventos = []
    if pre:
        eventos.append({'listen': 'prerequest', 'script': {'type': 'text/javascript', 'exec': lineas(pre)}})
    if tests:
        eventos.append({'listen': 'test', 'script': {'type': 'text/javascript', 'exec': lineas(tests)}})
    if eventos:
        item['event'] = eventos
    return item


def carpeta(nombre, descripcion, items):
    return {'name': nombre, 'description': descripcion, 'item': items}


# ---------------------------------------------------------------------------------
# 0 · Salud
# ---------------------------------------------------------------------------------
salud = carpeta(
    '0 · Salud',
    'Las tres piezas responden. Si algo acá falla, la demo no está levantada.',
    [
        pedido('proxy /health -> 200', 'GET', '/health', tests="""
pm.test('el proxy responde 200', () => pm.response.to.have.status(200));
pm.test('detrás del proxy contesta una instancia', () => pm.expect(pm.response.json().instancia).to.be.oneOf(['app1', 'app2']));
"""),
        pedido('app1 /health -> 200 (directo, sin proxy)', 'GET', '/health', base='app1Url', tests="""
pm.test('app1 responde 200', () => pm.response.to.have.status(200));
pm.test('es app1', () => pm.expect(pm.response.json().instancia).to.eql('app1'));
"""),
        pedido('app2 /health -> 200 (directo, sin proxy)', 'GET', '/health', base='app2Url', tests="""
pm.test('app2 responde 200', () => pm.response.to.have.status(200));
pm.test('es app2', () => pm.expect(pm.response.json().instancia).to.eql('app2'));
"""),
    ],
)

# ---------------------------------------------------------------------------------
# 1 · Seguridad — los cinco pedidos del guion (más uno de password incorrecta)
# ---------------------------------------------------------------------------------
RUTA = {'ruta': 'cinta-7'}
seguridad = carpeta(
    '1 · Seguridad (resistir ataques)',
    'Los cinco pedidos del guion de exposición, en orden. Cada uno es un acto discreto cuyo '
    'código de respuesta evidencia una táctica. Los logins guardan el token solos en la '
    'variable de colección: no hay que copiar y pegar nada en vivo.',
    [
        pedido('1 - PUT ruta SIN token -> 401 (autenticar actores)', 'PUT', '/api/equipaje/123/ruta', cuerpo=RUTA, tests="""
pm.test('401 sin credencial', () => pm.response.to.have.status(401));
pm.test('el error dice que falta el token', () => pm.expect(pm.response.json().error).to.eql('falta token'));
"""),
        pedido('2 - Login operador -> 200 + token (autenticar actores)', 'POST', '/auth/login',
               cuerpo={'usuario': 'operador', 'password': '1234'}, tests="""
pm.test('200 con credencial válida', () => pm.response.to.have.status(200));
pm.test('devuelve un token y el rol operador', () => {
  const r = pm.response.json();
  pm.expect(r.token).to.be.a('string').and.not.empty;
  pm.expect(r.rol).to.eql('operador');
});
pm.collectionVariables.set('token', pm.response.json().token);
pm.collectionVariables.set('tokenOperador', pm.response.json().token);
"""),
        pedido('2b - Login con password incorrecta -> 401 (autenticar actores)', 'POST', '/auth/login',
               cuerpo={'usuario': 'operador', 'password': 'incorrecta'}, tests="""
pm.test('401 con credencial inválida', () => pm.response.to.have.status(401));
pm.test('no devuelve token', () => pm.expect(pm.response.json().token).to.be.undefined);
"""),
        pedido('3 - PUT ruta con token de OPERADOR -> 403 (autorizar actores)', 'PUT', '/api/equipaje/123/ruta',
               cuerpo=RUTA, token=True, pre="""
// Por si se corre este pedido suelto: usa el token del operador guardado en el login.
if (pm.variables.get('tokenOperador')) pm.collectionVariables.set('token', pm.variables.get('tokenOperador'));
""", tests="""
pm.test('403 rol sin permiso', () => pm.response.to.have.status(403));
pm.test('el error nombra el rol del actor y el rol requerido', () => {
  const r = pm.response.json();
  pm.expect(r.rolDelActor).to.eql('operador');
  pm.expect(r.rolesRequeridos).to.include('supervisor');
});
"""),
        pedido('4 - Login supervisor -> 200 + token', 'POST', '/auth/login',
               cuerpo={'usuario': 'supervisor', 'password': '1234'}, tests="""
pm.test('200 con credencial válida', () => pm.response.to.have.status(200));
pm.test('rol supervisor', () => pm.expect(pm.response.json().rol).to.eql('supervisor'));
pm.collectionVariables.set('token', pm.response.json().token);
pm.collectionVariables.set('tokenSupervisor', pm.response.json().token);
"""),
        pedido('5 - PUT ruta con token de SUPERVISOR -> 200 (autorizar actores)', 'PUT', '/api/equipaje/123/ruta',
               cuerpo=RUTA, token=True, pre="""
if (pm.variables.get('tokenSupervisor')) pm.collectionVariables.set('token', pm.variables.get('tokenSupervisor'));
""", tests="""
pm.test('200 ruta modificada', () => pm.response.to.have.status(200));
pm.test('la modificó el supervisor', () => {
  const r = pm.response.json();
  pm.expect(r.modificadaPor).to.eql('supervisor');
  pm.expect(r.rutaNueva).to.eql('cinta-7');
});
// Mismo endpoint, mismo sistema, distinta identidad: 403 en el pedido 3, 200 acá.
"""),
    ],
)

# ---------------------------------------------------------------------------------
# 2 · Disponibilidad — reemplaza a verificar.sh: el pico se dispara desde Postman
# ---------------------------------------------------------------------------------
PRE_PICO = """
// Dispara N pedidos EN PARALELO contra el proxy y guarda los headers de evidencia.
// app1 admite 5 pedidos concurrentes (MAX_CONCURRENTES): del sexto en adelante responde
// 503, Nginx reintenta contra app2 (backup) y el cliente recibe 200 igual.
// Postman espera a que terminen todos los pm.sendRequest antes de mandar este pedido.
const N = Number(pm.variables.get('pico') || 20);
const base = pm.variables.get('baseUrl');
const token = pm.variables.get('token');
const estados = [], instancias = [], tiempos = [], codigos = [], cuerpos = [];
let pendientes = N;

for (let i = 1; i <= N; i++) {
  pm.sendRequest({
    url: `${base}/api/equipaje/${i}/scan`,
    method: 'GET',
    header: { Authorization: `Bearer ${token}` },
  }, (err, res) => {
    if (err) {
      codigos.push('ERR'); estados.push(''); instancias.push(''); tiempos.push(''); cuerpos.push('');
    } else {
      codigos.push(res.code);
      estados.push((res.headers.get('X-Estados') || '').trim());
      instancias.push((res.headers.get('X-Instancias-Probadas') || '').trim());
      tiempos.push((res.headers.get('X-Tiempo-Total') || '').trim());
      let inst = '';
      try { inst = res.json().instancia || ''; } catch (e) {}
      cuerpos.push(inst);
    }
    if (--pendientes === 0) {
      pm.variables.set('picoCodigos', JSON.stringify(codigos));
      pm.variables.set('picoEstados', JSON.stringify(estados));
      pm.variables.set('picoInstancias', JSON.stringify(instancias));
      pm.variables.set('picoTiempos', JSON.stringify(tiempos));
      pm.variables.set('picoCuerpos', JSON.stringify(cuerpos));
    }
  });
}
"""

TESTS_PICO = """
const codigos = JSON.parse(pm.variables.get('picoCodigos') || '[]');
const estados = JSON.parse(pm.variables.get('picoEstados') || '[]');
const instancias = JSON.parse(pm.variables.get('picoInstancias') || '[]');
const tiempos = JSON.parse(pm.variables.get('picoTiempos') || '[]');
const cuerpos = JSON.parse(pm.variables.get('picoCuerpos') || '[]');
const N = Number(pm.variables.get('pico') || 20);

// Índices de las respuestas que muestran reintento + failover ("503, 200").
const conConmutacion = estados.map((e, i) => i).filter(i => estados[i].includes(','));
const porApp1 = cuerpos.filter(c => c === 'app1').length;
const porApp2 = cuerpos.filter(c => c === 'app2').length;

console.log(`Pico de ${estados.length} pedidos en paralelo: ${porApp1} los atendió app1, ${porApp2} app2, ` +
            `${conConmutacion.length} llevaron reintento + conmutación.`);
if (conConmutacion.length) {
  const i = conConmutacion[0];
  console.log('Evidencia (una respuesta):');
  console.log(`  X-Instancias-Probadas: ${instancias[i]}`);
  console.log(`  X-Estados:             ${estados[i]}`);
  console.log(`  X-Tiempo-Total:        ${tiempos[i]}`);
}

pm.test(`se dispararon ${N} pedidos en paralelo y todos volvieron`, () => {
  pm.expect(estados.length).to.eql(N);
});
pm.test('el cliente NUNCA vio un error: los ' + N + ' pedidos terminaron en 200', () => {
  pm.expect(codigos.every(c => c === 200), `códigos: ${codigos.join(',')}`).to.be.true;
});
pm.test('REINTENTOS: al menos una respuesta muestra "503, 200" en X-Estados', () => {
  pm.expect(conConmutacion.length, 'respuestas con dos estados').to.be.above(0);
  pm.expect(estados[conConmutacion[0]]).to.match(/^503,\\s*200$/);
});
pm.test('REPUESTO REDUNDANTE: esa misma respuesta probó dos instancias (primario y backup)', () => {
  const i = conConmutacion[0];
  pm.expect(instancias[i].split(',').length).to.eql(2);
});
pm.test('el repuesto atendió pedidos que el primario rechazó', () => {
  pm.expect(porApp2, 'pedidos atendidos por app2').to.be.above(0);
});
pm.test('CA-1: la conmutación al repuesto tardó menos de 2 s', () => {
  const i = conConmutacion[0];
  const total = tiempos[i].split(',').map(Number).reduce((a, b) => a + b, 0);
  pm.expect(total, `X-Tiempo-Total: ${tiempos[i]}`).to.be.below(2);
});

// El pedido "principal" de este ítem es un scan más, mandado después del pico.
pm.test('este pedido también dio 200', () => pm.response.to.have.status(200));
console.log(`Este pedido lo atendió ${pm.response.json().instancia}: ` +
            `X-Instancias-Probadas=${pm.response.headers.get('X-Instancias-Probadas')} ` +
            `X-Estados=${pm.response.headers.get('X-Estados')}`);
"""

disponibilidad = carpeta(
    '2 · Disponibilidad (recuperarse de fallas)',
    'Hace desde Postman lo que antes hacía verificar.sh: mira el estado normal, dispara un '
    'pico de pedidos en paralelo, y comprueba en los headers del proxy que hubo reintento y '
    'conmutación al repuesto. Correr la carpeta entera y en orden (Run folder). '
    'Requiere haber hecho login antes (carpeta 1) o correr la colección completa.',
    [
        pedido('1 - app2 /stats antes del pico (repuesto warm: encendido, sin tráfico)', 'GET', '/stats', base='app2Url', pre="""
// Si se corre la carpeta suelta, conseguir un token primero.
if (!pm.variables.get('token')) {
  pm.sendRequest({
    url: `${pm.variables.get('baseUrl')}/auth/login`, method: 'POST',
    header: { 'Content-Type': 'application/json' },
    body: { mode: 'raw', raw: JSON.stringify({ usuario: 'operador', password: '1234' }) },
  }, (err, res) => { if (!err) pm.collectionVariables.set('token', res.json().token); });
}
""", tests="""
pm.test('app2 responde /stats', () => pm.response.to.have.status(200));
const s = pm.response.json();
pm.test('es la instancia app2', () => pm.expect(s.instancia).to.eql('app2'));
pm.variables.set('atendidosAntes', s.atendidos);
console.log(`app2 antes del pico: atendidos=${s.atendidos} (0 recién reiniciada = repuesto warm)`);
"""),
        pedido('2 - Scan en operación normal -> una sola instancia, X-Estados: 200', 'GET', '/api/equipaje/1/scan', token=True, tests="""
pm.test('200 en operación normal', () => pm.response.to.have.status(200));
const inst = pm.response.headers.get('X-Instancias-Probadas') || '';
const est = pm.response.headers.get('X-Estados') || '';
const t = pm.response.headers.get('X-Tiempo-Total') || '';
pm.test('los tres headers de evidencia están presentes', () => {
  pm.expect(inst, 'X-Instancias-Probadas').to.not.be.empty;
  pm.expect(est, 'X-Estados').to.not.be.empty;
  pm.expect(t, 'X-Tiempo-Total').to.not.be.empty;
});
pm.test('sin carga se prueba UNA sola instancia y el estado es 200', () => {
  pm.expect(inst).to.not.include(',');
  pm.expect(est.trim()).to.eql('200');
});
pm.test("X-Tiempo-Total trae un número, no '-'", () => pm.expect(t).to.match(/[0-9]/));
console.log(`Operación normal: atendió ${pm.response.json().instancia} · X-Instancias-Probadas=${inst} · X-Estados=${est} · X-Tiempo-Total=${t}`);
"""),
        pedido('3 - PICO: {{pico}} pedidos en paralelo -> X-Estados: 503, 200 (reintentos + repuesto redundante)',
               'GET', '/api/equipaje/123/scan', token=True, pre=PRE_PICO, tests=TESTS_PICO,
               descripcion='El pre-request dispara `pico` pedidos en paralelo (20 por defecto) y guarda los '
                           'headers de evidencia; los tests comprueban las dos tácticas y el criterio CA-1.'),
        pedido('4 - app2 /stats después del pico -> atendió pedidos', 'GET', '/stats', base='app2Url', tests="""
pm.test('app2 responde /stats', () => pm.response.to.have.status(200));
const antes = Number(pm.variables.get('atendidosAntes') || 0);
const despues = pm.response.json().atendidos;
pm.test(`el contador de app2 se movió (${antes} -> ${despues}): hubo failover`, () => {
  pm.expect(despues).to.be.above(antes);
});
"""),
        pedido('5 - Recuperación: pasado fail_timeout el tráfico vuelve solo al primario', 'GET', '/api/equipaje/1/scan', token=True, pre="""
// Nginx marca caído a app1 durante fail_timeout=10s después de dos fallas. Pasado ese
// tiempo vuelve a probarlo y el tráfico regresa al primario sin intervención manual.
const espera = Number(pm.variables.get('esperaRecuperacionMs') || 11000);
console.log(`Esperando ${espera / 1000} s (fail_timeout de Nginx) para ver la recuperación del primario...`);
setTimeout(() => {}, espera);
""", tests="""
pm.test('200 después de la recuperación', () => pm.response.to.have.status(200));
const inst = pm.response.headers.get('X-Instancias-Probadas') || '';
pm.test('lo atendió el primario (app1) otra vez', () => pm.expect(pm.response.json().instancia).to.eql('app1'));
pm.test('una sola instancia probada, sin reintento', () => {
  pm.expect(inst).to.not.include(',');
  pm.expect((pm.response.headers.get('X-Estados') || '').trim()).to.eql('200');
});
console.log(`Recuperado: atendió ${pm.response.json().instancia} · X-Instancias-Probadas=${inst}`);
"""),
    ],
)

coleccion = {
    'info': {
        'name': 'AeroSur - TFU tácticas de arquitectura',
        'description': (
            'Verificación completa de las cuatro tácticas de la demo (Grupo 5 · caso AeroSur · '
            'PUC-01 Transportar equipaje) sin scripts de shell.\n\n'
            '- **0 · Salud**: las tres piezas responden.\n'
            '- **1 · Seguridad**: autenticar actores (401 / 200 + token) y autorizar actores (403 / 200).\n'
            '- **2 · Disponibilidad**: reintentos y repuesto redundante, disparando el pico desde Postman '
            'y leyendo los headers de evidencia del proxy.\n\n'
            'Correr la colección entera con *Run collection* (o `newman`). Las carpetas 1 y 2 también '
            'se pueden correr sueltas. Variables: `baseUrl` (proxy), `app1Url`, `app2Url` (instancias '
            'directas, sólo para /stats y /health), `pico` (pedidos en paralelo), `esperaRecuperacionMs`.'
        ),
        'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
    },
    'variable': [
        {'key': 'baseUrl', 'value': 'http://localhost:8080'},
        {'key': 'app1Url', 'value': 'http://localhost:3001'},
        {'key': 'app2Url', 'value': 'http://localhost:3002'},
        {'key': 'token', 'value': ''},
        {'key': 'tokenOperador', 'value': ''},
        {'key': 'tokenSupervisor', 'value': ''},
        {'key': 'pico', 'value': '20'},
        {'key': 'esperaRecuperacionMs', 'value': '11000'},
    ],
    'item': [salud, seguridad, disponibilidad],
}

SALIDA.write_text(json.dumps(coleccion, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'escrita {SALIDA.name}')
