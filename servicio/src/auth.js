// Tácticas de seguridad (categoría: resistir ataques)
//   - autenticar actores: login que emite un JWT firmado + verificación en cada pedido
//   - autorizar actores:  comparación del claim `rol` contra los roles permitidos del endpoint
const jwt = require('jsonwebtoken');

const SECRETO = process.env.SECRETO || 'demo-aerosur';

// Simplificación explícita de la demo: usuarios en memoria, sin base de datos.
// La táctica que se demuestra es la verificación de identidad, no su almacenamiento.
const USUARIOS = {
  operador:   { pass: '1234', rol: 'operador'   },
  supervisor: { pass: '1234', rol: 'supervisor' },
};

// táctica: autenticar actores (emisión de credencial)
function login(req, res) {
  const { usuario, password } = req.body || {};
  const u = USUARIOS[usuario];
  if (!u || u.pass !== password) {
    return res.status(401).json({ error: 'credenciales inválidas' });
  }
  const token = jwt.sign({ usuario, rol: u.rol }, SECRETO, { expiresIn: '1h' });
  res.json({ token, rol: u.rol });
}

// táctica: autenticar actores (verificación en cada pedido)
function autenticar(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'falta token' });
  try {
    req.actor = jwt.verify(token, SECRETO);
    next();
  } catch {
    res.status(401).json({ error: 'token inválido' });
  }
}

// táctica: autorizar actores
function autorizar(...rolesPermitidos) {
  return (req, res, next) => {
    if (!rolesPermitidos.includes(req.actor.rol)) {
      return res.status(403).json({
        error: 'rol sin permiso para esta operación',
        rolDelActor: req.actor.rol,
        rolesRequeridos: rolesPermitidos,
      });
    }
    next();
  };
}

module.exports = { login, autenticar, autorizar };
