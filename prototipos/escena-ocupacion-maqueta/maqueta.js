// Maqueta de papel de la sede: el edificio no lleva color, solo las personas.
import * as T from 'three';

const estilos = getComputedStyle(document.documentElement);
const token = nombre => estilos.getPropertyValue(nombre).trim();
const papel50 = token('--color-papel-50');
const papel100 = token('--color-papel-100');
const papel200 = token('--color-papel-200');
const papel400 = token('--color-papel-400');
const tinta400 = token('--color-tinta-400');
const tinta600 = token('--color-tinta-600');

const TEMAS = {
  noche: {
    hemisferio: ['#6b6470', '#1e1b16', .8], sol: ['#b9c0d2', .55], relleno: 1.1, brilloFigura: 1.7, estela: '#fff4e4', focoBase: 250, focoPorVisita: 18, exposicion: 1,
    ventana: 2.4, visita: token('--color-bosque-300'), simulada: token('--color-terracota-400'), conciliar: token('--color-mostaza-300'),
  },
  dia: {
    hemisferio: ['#fffdf9', '#c9bfae', 1.75], sol: ['#fff0da', 3.1], relleno: .5, brilloFigura: 1, estela: tinta600, focoBase: 0, focoPorVisita: 9, exposicion: .95,
    ventana: 0, visita: token('--color-bosque-700'), simulada: token('--color-terracota-600'), conciliar: token('--color-mostaza-600'),
  },
};

// Plano de la sede, en metros: x hacia el este, z hacia la puerta.
const CARRIL = -.5;
const PUERTA = {x: CARRIL, z: 15.5};
const SALAS = {
  'Musculación': {x0: -18, x1: -3, z0: -13, z1: 0, pasillo: -6, puertaX: -3},
  'Peso libre': {x0: 2, x1: 18, z0: -13, z1: -2, pasillo: -8, puertaX: 2},
  'Cardio': {x0: -18, x1: -3, z0: 0, z1: 13, pasillo: 6, puertaX: -3},
  'Funcional': {x0: 2, x1: 18, z0: -2, z1: 13, pasillo: 6, puertaX: 2},
  'En la sede': {x0: -3, x1: 2, z0: -13, z1: 13, pasillo: null, puertaX: CARRIL},
};
const NOMBRES = Object.keys(SALAS);

// --- Piezas estáticas: una sola malla instanciada por forma, un solo dibujo por cuadro de sombra ---
const piezas = {caja: [], cilindro: [], ventana: [], esfera: []};
const auxiliar = new T.Object3D();
const color = new T.Color();

function pieza(forma, x, y, z, ancho, alto, fondo, tinte, giroY = 0, giroZ = 0) {
  piezas[forma].push({x, y, z, ancho, alto, fondo, tinte, giroY, giroZ});
}
function caja(x, base, z, ancho, alto, fondo, tinte = papel100, giro = 0) {
  pieza('caja', x, base + alto / 2, z, ancho, alto, fondo, tinte, giro);
}
// Barra horizontal a lo largo de x.
function barra(x, y, z, largo, radio, tinte = tinta600) {
  pieza('cilindro', x, y, z, radio * 2, largo, radio * 2, tinte, 0, Math.PI / 2);
}
function poste(x, base, z, radio, alto, tinte = papel100) {
  pieza('cilindro', x, base + alto / 2, z, radio * 2, alto, radio * 2, tinte);
}
function muro(x0, z0, x1, z1, alto, huecos = []) {
  const esX = z0 === z1;
  const [inicio, fin] = esX ? [x0, x1] : [z0, z1];
  const tramos = [];
  let desde = inicio;
  for (const [a, b] of huecos) { tramos.push([desde, a]); desde = b; }
  tramos.push([desde, fin]);
  for (const [a, b] of tramos) {
    if (b - a <= 0) continue;
    const medio = (a + b) / 2;
    if (esX) caja(medio, 0, z0, b - a, alto, .28, papel50);
    else caja(x0, 0, medio, .28, alto, b - a, papel50);
  }
}

function construirEdificio() {
  // Tablero de la maqueta, vereda y árboles de papel.
  caja(0, -1.2, 1.4, 45, 1.2, 35, tinta400);
  caja(CARRIL, -.02, 16.5, 5, .06, 6, papel50);
  for (const [x, z, r] of [[-20, 15.5, 1], [-14, 16.6, .75], [8, 16.8, .85], [14, 15.6, 1.05], [20.4, 8, .8], [20.6, -4, 1]]) {
    poste(x, 0, z, .07, 1.2, papel50);
    pieza('esfera', x, 1.2 + r * .7, z, r * 2, r * 2, r * 2, papel50);
  }

  // Muros: los del fondo altos con ventanas; los del frente bajos, para ver adentro.
  const altoFondo = 3.4;
  const bajo = .55;
  for (let x = -16; x <= 16; x += 4) {
    if (Math.abs(x) < 3) continue;
    pieza('ventana', x, 2.1, -13, 2.6, 1.5, .32, '#ffffff');
  }
  for (let z = -10; z <= 10; z += 4) pieza('ventana', -18, 2.1, z, .32, 1.5, 2.6, '#ffffff');
  muro(-18, -13, 18, -13, altoFondo);
  muro(-18, -13, -18, 13, altoFondo);
  muro(-18, 13, 18, 13, bajo, [[CARRIL - 1.7, CARRIL + 1.7]]);
  muro(18, -13, 18, 13, bajo);
  // Paredes interiores, bajas, con una puerta sobre cada pasillo.
  muro(-3, -13, -3, 13, .95, [[-7.6, -4.4], [4.4, 7.6]]);
  muro(2, -13, 2, 13, .95, [[-9.6, -6.4], [4.4, 7.6]]);
  muro(-18, 0, -3, 0, .95, [[-11.5, -8.5]]);
  muro(2, -2, 18, -2, .95, [[9, 12]]);
  // Pórtico de la puerta.
  caja(CARRIL - 1.8, 0, 13, .3, 2.7, .4, papel50);
  caja(CARRIL + 1.8, 0, 13, .3, 2.7, .4, papel50);
  caja(CARRIL, 2.7, 13, 4, .28, .55, papel50);

  // Recepción: mostrador junto a la puerta y bancos a lo largo del pasillo.
  caja(-2.35, 0, 10.6, .85, 1.05, 3, papel50);
  caja(-2.35, 1.05, 10.6, 1.05, .08, 3.2, papel200);
  for (const [z, x] of [[1, -2.55], [-1.5, -2.55], [-10.5, -2.55], [-3, 1.6], [0, 1.6], [-11.5, 1.6]]) caja(x, 0, z, .55, .42, 1.7, papel400);
}

function cinta(x, z) {
  caja(x, 0, z, .85, .18, 1.9, tinta400);
  caja(x, .18, z, .62, .03, 1.65, tinta600);
  caja(x - .36, 0, z + .78, .07, 1.2, .07, papel100);
  caja(x + .36, 0, z + .78, .07, 1.2, .07, papel100);
  caja(x, 1.15, z + .85, .8, .22, .12, papel50);
}
function bicicleta(x, z) {
  caja(x, 0, z, .55, .12, 1.25, tinta400);
  poste(x, .1, z - .3, .05, .62, papel100);
  caja(x, .72, z - .3, .3, .08, .4, tinta600);
  poste(x, .1, z + .42, .05, .92, papel100);
  barra(x, 1.02, z + .42, .55, .035, papel100);
  pieza('cilindro', x, .38, z + .15, .55, .1, .55, tinta600, 0, Math.PI / 2);
}
function maquina(x, z, sentido) {
  caja(x, 0, z, 1.05, .1, 1.5, tinta400);
  caja(x, .1, z - sentido * .55, 1, 1.75, .14, papel100);
  caja(x, .25, z - sentido * .55, .55, .7, .18, tinta600);
  caja(x, .5, z + sentido * .12, .55, .12, .75, tinta600);
  caja(x, .6, z - sentido * .34, .55, .72, .1, tinta600);
  caja(x, 1.75, z - sentido * .15, 1, .08, .9, papel100);
}
function rack(x, z) {
  caja(x, 0, z, 2.3, .06, 2.1, papel400);
  for (const [dx, dz] of [[-.95, -.8], [.95, -.8], [-.95, .1], [.95, .1]]) poste(x + dx, .06, z + dz, .05, 2.3, papel50);
  barra(x, 2.33, z - .8, 2, .04, papel50);
  barra(x, 2.33, z + .1, 2, .04, papel50);
  barra(x, 1.3, z - .1, 2.5, .03);
  for (const lado of [-1.1, 1.1]) pieza('cilindro', x + lado, 1.3, z - .1, .62, .11, .62, tinta600, 0, Math.PI / 2);
}
function banco(x, z) {
  caja(x, 0, z, .42, .36, 1.3, papel100);
  caja(x, .36, z, .46, .09, 1.35, tinta600);
  poste(x - .45, 0, z - .78, .04, 1, papel50);
  poste(x + .45, 0, z - .78, .04, 1, papel50);
  barra(x, 1, z - .78, 1.5, .03);
}

function construirEquipos() {
  const lugares = Object.fromEntries(NOMBRES.map(n => [n, []]));
  const anotar = (zona, x, z, giro) => lugares[zona].push({x, z, giro});

  for (let x = -16; x <= -5; x += 2.2) {
    maquina(x, -11, 1); anotar('Musculación', x, -10.45, 0);
    maquina(x, -8.4, 1); anotar('Musculación', x, -7.85, 0);
    maquina(x, -2, -1); anotar('Musculación', x, -2.55, Math.PI);
    anotar('Musculación', x + .9, -4.25, Math.PI / 2);
  }
  for (let x = -16.2; x <= -5; x += 2.2) {
    cinta(x, 11); anotar('Cardio', x, 11, 0);
    cinta(x, 8.4); anotar('Cardio', x, 8.4, 0);
    bicicleta(x, 3.4); anotar('Cardio', x, 3.35, 0);
    bicicleta(x, 1.3); anotar('Cardio', x, 1.25, 0);
  }
  for (let x = 4.6; x <= 16; x += 3.7) {
    rack(x, -11); anotar('Peso libre', x, -10.9, 0);
    anotar('Peso libre', x + 1.4, -9.5, Math.PI / 2);
  }
  for (let x = 4; x <= 16; x += 2.4) {
    banco(x, -4.6); anotar('Peso libre', x, -5.8, 0);
    anotar('Peso libre', x + 1, -3, Math.PI);
  }
  caja(17.3, 0, -7.5, .75, .9, 9, papel400);
  caja(17.3, .9, -7.5, .55, .7, 9, papel200);
  for (let z = -11.4; z <= -3.6; z += .75) {
    barra(17.3, .98, z, .55, .05);
    barra(17.3, 1.66, z, .45, .045);
  }

  // Funcional: tapiz, jaula y cajones de salto.
  caja(10, 0, 10.2, 13.6, .05, 5, papel400);
  for (let x = 4.6; x <= 15.2; x += 2.65) {
    for (const z of [8.5, 10.2, 11.9]) anotar('Funcional', x, z, Math.PI);
    anotar('Funcional', x, 3.3, 0);
    anotar('Funcional', x + 1, 1.3, 0);
  }
  for (let x = 4.5; x <= 15.5; x += 2.75) {
    poste(x, 0, -.8, .06, 2.6, papel50);
    poste(x, 0, .5, .06, 2.6, papel50);
    barra(x + 1.37, 2.6, -.8, 2.75, .05, papel50);
    barra(x + 1.37, 2.6, .5, 2.75, .05, papel50);
    if (x < 15) barra(x + 1.37, 2.1, -.15, 2.75, .03);
  }
  for (const [x, alto] of [[16.6, .9], [16.6, .55]]) caja(x, 0, alto > .6 ? 3.6 : 2.5, .9, alto, .9, papel100);
  caja(16.6, 0, 8, .8, .34, 2.2, tinta400);

  // En la sede: dos filas a los lados del carril central, que queda libre para caminar.
  for (let z = -11.8; z <= 3.5; z += 1.4) {
    if (z < -4 || z > -8) if (!(z > -7.8 && z < -4.2)) anotar('En la sede', -2.15, z, Math.PI / 2);
  }
  for (let z = -11.8; z <= 11.8; z += 1.4) {
    if (!(z > -9.8 && z < -6.2) && !(z > 4.2 && z < 7.8)) anotar('En la sede', 1.15, z, -Math.PI / 2);
  }
  return lugares;
}

function cuadroPiso() {
  const escala = 56;
  const lienzo = document.createElement('canvas');
  lienzo.width = 36 * escala;
  lienzo.height = 26 * escala;
  const c = lienzo.getContext('2d');
  c.scale(escala, escala);
  c.translate(18, 13);
  c.fillStyle = papel200;
  c.fillRect(-18, -13, 36, 26);

  const tonos = {'Musculación': '#d8ccb9', 'Peso libre': '#cfc2ae', 'Cardio': '#e7dcc9', 'Funcional': '#ded3c0', 'En la sede': '#f3ecdf'};
  for (const nombre of NOMBRES) {
    const s = SALAS[nombre];
    c.fillStyle = tonos[nombre];
    c.fillRect(s.x0, s.z0, s.x1 - s.x0, s.z1 - s.z0);
  }
  // Baldosas de caucho en las salas de fuerza, tablas en cardio.
  c.strokeStyle = '#1e1b1614';
  c.lineWidth = .025;
  for (const nombre of ['Musculación', 'Peso libre']) {
    const s = SALAS[nombre];
    for (let x = s.x0; x <= s.x1; x += 1) { c.beginPath(); c.moveTo(x, s.z0); c.lineTo(x, s.z1); c.stroke(); }
    for (let z = s.z0; z <= s.z1; z += 1) { c.beginPath(); c.moveTo(s.x0, z); c.lineTo(s.x1, z); c.stroke(); }
  }
  const cardio = SALAS.Cardio;
  for (let z = cardio.z0; z <= cardio.z1; z += .5) { c.beginPath(); c.moveTo(cardio.x0, z); c.lineTo(cardio.x1, z); c.stroke(); }

  // Sombra de contacto al pie de cada muro: es lo que hace que parezca un objeto.
  for (const nombre of NOMBRES) {
    const s = SALAS[nombre];
    const bordes = [
      [s.x0, s.z0, s.x0 + 1.6, s.z0, s.x0, s.z0, 1.6, s.z1 - s.z0],
      [s.x1, s.z0, s.x1 - 1.6, s.z0, s.x1 - 1.6, s.z0, 1.6, s.z1 - s.z0],
      [s.x0, s.z0, s.x0, s.z0 + 1.6, s.x0, s.z0, s.x1 - s.x0, 1.6],
      [s.x0, s.z1, s.x0, s.z1 - 1.6, s.x0, s.z1 - 1.6, s.x1 - s.x0, 1.6],
    ];
    for (const [ax, az, bx, bz, x, z, ancho, alto] of bordes) {
      const g = c.createLinearGradient(ax, az, bx, bz);
      g.addColorStop(0, '#1e1b1647');
      g.addColorStop(1, '#1e1b1600');
      c.fillStyle = g;
      c.fillRect(x, z, ancho, alto);
    }
  }
  // Grano de cartón.
  c.setTransform(1, 0, 0, 1, 0, 0);
  for (let i = 0; i < 26000; i++) {
    c.fillStyle = i % 2 ? '#ffffff0a' : '#0000000a';
    c.fillRect(Math.random() * lienzo.width, Math.random() * lienzo.height, 2, 2);
  }
  const textura = new T.CanvasTexture(lienzo);
  textura.colorSpace = T.SRGBColorSpace;
  textura.anisotropy = 8;
  return textura;
}

// --- Escena ---
const lienzo = document.querySelector('canvas');
const contenedorEscena = document.querySelector('.escena');
let dibujante;
try {
  dibujante = new T.WebGLRenderer({canvas: lienzo, antialias: true, alpha: true});
} catch {
  document.documentElement.dataset.sinWebgl = '';
  lienzo.hidden = true;
}

const escena = new T.Scene();
const camara = new T.OrthographicCamera(-1, 1, 1, -1, .1, 400);
const DIRECCION = new T.Vector3(1, 1.02, 1).normalize();
const vista = {x: .6, z: 1.2, zoom: 1, destino: null};
const reducido = matchMedia('(prefers-reduced-motion: reduce)');

const lugares = construirEquipos();
construirEdificio();

function mallaInstanciada(geometria, material, lista) {
  const malla = new T.InstancedMesh(geometria, material, lista.length);
  lista.forEach((p, i) => {
    auxiliar.position.set(p.x, p.y, p.z);
    auxiliar.rotation.set(0, p.giroY, p.giroZ);
    auxiliar.scale.set(p.ancho, p.alto, p.fondo);
    auxiliar.updateMatrix();
    malla.setMatrixAt(i, auxiliar.matrix);
    malla.setColorAt(i, color.set(p.tinte));
  });
  malla.castShadow = true;
  malla.receiveShadow = true;
  malla.frustumCulled = false;
  escena.add(malla);
  return malla;
}
mallaInstanciada(new T.BoxGeometry(1, 1, 1), new T.MeshStandardMaterial({roughness: .92}), piezas.caja);
mallaInstanciada(new T.CylinderGeometry(.5, .5, 1, 16), new T.MeshStandardMaterial({roughness: .8}), piezas.cilindro);
mallaInstanciada(new T.IcosahedronGeometry(.5, 1), new T.MeshStandardMaterial({roughness: .95, flatShading: true}), piezas.esfera);
const materialVentana = new T.MeshStandardMaterial({color: '#cfc7b8', emissive: '#ffc98a', emissiveIntensity: 2, roughness: .4});
const ventanas = mallaInstanciada(new T.BoxGeometry(1, 1, 1), materialVentana, piezas.ventana);
ventanas.castShadow = false;

const piso = new T.Mesh(new T.PlaneGeometry(36, 26), new T.MeshStandardMaterial({map: cuadroPiso(), roughness: .95}));
piso.rotation.x = -Math.PI / 2;
piso.position.y = .02;
piso.receiveShadow = true;
escena.add(piso);

const hemisferio = new T.HemisphereLight();
escena.add(hemisferio);
const sol = new T.DirectionalLight();
sol.position.set(34, 42, 6);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, {left: -34, right: 34, top: 34, bottom: -34, near: 1, far: 120});
sol.shadow.bias = -.0004;
sol.shadow.radius = 3;
escena.add(sol);
// Relleno desde la cámara: despega las figuras del piso, que el foco solo ilumina desde arriba.
const relleno = new T.DirectionalLight('#fff4e4');
relleno.position.copy(DIRECCION).multiplyScalar(50);
escena.add(relleno);

// Un foco por zona de la sede: la luz sube con la gente que hay adentro.
const focos = {};
for (const nombre of NOMBRES) {
  const s = SALAS[nombre];
  const cx = (s.x0 + s.x1) / 2;
  const cz = (s.z0 + s.z1) / 2;
  const foco = new T.SpotLight('#ffd3a0', 0, 60, Math.atan(Math.max(s.x1 - s.x0, s.z1 - s.z0) * .72 / 15), .85, 1.6);
  foco.position.set(cx, 15, cz);
  foco.target.position.set(cx, 0, cz);
  foco.castShadow = true;
  foco.shadow.mapSize.set(1024, 1024);
  foco.shadow.bias = -.0006;
  foco.shadow.radius = 4;
  foco.shadow.camera.near = 4;
  foco.shadow.camera.far = 30;
  escena.add(foco, foco.target);
  focos[nombre] = {luz: foco, actual: 0};
}

// Resplandor de la puerta: se enciende con cada entrada o salida.
const lienzoHalo = document.createElement('canvas');
lienzoHalo.width = lienzoHalo.height = 128;
const contextoHalo = lienzoHalo.getContext('2d');
const degradeHalo = contextoHalo.createRadialGradient(64, 64, 0, 64, 64, 64);
degradeHalo.addColorStop(0, '#ffe0b0ff');
degradeHalo.addColorStop(1, '#ffe0b000');
contextoHalo.fillStyle = degradeHalo;
contextoHalo.fillRect(0, 0, 128, 128);
const halo = new T.Sprite(new T.SpriteMaterial({map: new T.CanvasTexture(lienzoHalo), blending: T.AdditiveBlending, depthWrite: false, transparent: true}));
halo.position.set(CARRIL, 1.5, 13.4);
halo.scale.setScalar(7);
escena.add(halo);
let brilloPuerta = 0;

// --- Figuras de escala: torso, piernas y cabeza como en una maqueta de arquitecto ---
const CAPACIDAD = 96;
const materialFigura = new T.MeshStandardMaterial({roughness: .55});
const malla = (geometria, n = CAPACIDAD) => {
  const m = new T.InstancedMesh(geometria, materialFigura, n);
  m.castShadow = true;
  m.frustumCulled = false;
  m.setColorAt(0, color.set('#fff'));
  escena.add(m);
  return m;
};
const torsos = malla(new T.CapsuleGeometry(.27, .62, 4, 10));
const piernas = malla(new T.CapsuleGeometry(.1, .62, 3, 6), CAPACIDAD * 2);
const cabezas = malla(new T.SphereGeometry(.23, 14, 10));
const rombos = malla(new T.OctahedronGeometry(.31));
const anillos = new T.InstancedMesh(new T.RingGeometry(.52, .68, 28).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({transparent: true}), CAPACIDAD);
anillos.frustumCulled = false;
anillos.setColorAt(0, color.set('#fff'));
escena.add(anillos);
const seleccionado = new T.Mesh(new T.RingGeometry(.66, .98, 36).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({color: token('--color-tinta-950'), depthTest: false, transparent: true, toneMapped: false}));
seleccionado.visible = false;
seleccionado.renderOrder = 5;
escena.add(seleccionado);

// --- Estado ---
const datos = await (await fetch('../escena-ocupacion/personas.json')).json();
let tema = TEMAS.noche;
let personas = [];
let seleccion = null;
let zonaAbierta = null;
let objetivo = 40;
let siguienteId = 41;
let pausado = false;
let turno = 0;
const estelas = [];

const $ = selector => document.querySelector(selector);
const capaPersonas = $('#personas');
const tarjeta = $('#tarjeta');
const evento = $('#evento');
const azar = n => Math.floor(Math.random() * n);

function lugarLibre(zona) {
  const usados = new Set(personas.filter(p => p.zona === zona && !p.saliendo).map(p => p.lugar));
  const libres = lugares[zona].filter(l => !usados.has(l));
  if (libres.length) return libres[azar(libres.length)];
  // Sala llena: alguien de pie en el pasillo de la zona.
  const s = SALAS[zona];
  return {x: s.x0 + 1.5 + Math.random() * (s.x1 - s.x0 - 3), z: s.pasillo ?? (s.z0 + Math.random() * 20), giro: 0};
}

// Ruta real por el carril central y las puertas, nunca a través de los muros.
function tramoHastaCarril(desde, zona, carril) {
  const s = SALAS[zona];
  if (s.pasillo === null) return [{x: carril, z: desde.z}];
  return [{x: desde.x, z: s.pasillo}, {x: s.puertaX, z: s.pasillo}, {x: carril, z: s.pasillo}];
}
function ruta(desde, zonaDesde, hasta, zonaHasta) {
  const carril = CARRIL + (Math.random() - .5) * 1.1;
  const puntos = [desde];
  if (zonaDesde) puntos.push(...tramoHastaCarril(desde, zonaDesde, carril));
  else puntos.push({x: carril, z: desde.z});
  if (zonaHasta) puntos.push(...tramoHastaCarril(hasta, zonaHasta, carril).reverse());
  else puntos.push({x: carril, z: hasta.z});
  puntos.push(hasta);
  return suavizar(puntos);
}
// Redondea las esquinas para que nadie gire en seco.
function suavizar(puntos) {
  const limpios = puntos.filter((p, i) => i === 0 || Math.hypot(p.x - puntos[i - 1].x, p.z - puntos[i - 1].z) > .05);
  const salida = [limpios[0]];
  for (let i = 1; i < limpios.length - 1; i++) {
    const [a, b, c] = [limpios[i - 1], limpios[i], limpios[i + 1]];
    const la = Math.hypot(a.x - b.x, a.z - b.z);
    const lc = Math.hypot(c.x - b.x, c.z - b.z);
    const r = Math.min(1.1, la / 2, lc / 2);
    const inicio = {x: b.x + (a.x - b.x) * r / la, z: b.z + (a.z - b.z) * r / la};
    const fin = {x: b.x + (c.x - b.x) * r / lc, z: b.z + (c.z - b.z) * r / lc};
    for (let t = 0; t <= 1; t += .25) {
      const u = 1 - t;
      salida.push({x: u * u * inicio.x + 2 * u * t * b.x + t * t * fin.x, z: u * u * inicio.z + 2 * u * t * b.z + t * t * fin.z});
    }
  }
  salida.push(limpios.at(-1));
  return salida;
}
function largos(camino) {
  const acumulado = [0];
  for (let i = 1; i < camino.length; i++) acumulado.push(acumulado[i - 1] + Math.hypot(camino[i].x - camino[i - 1].x, camino[i].z - camino[i - 1].z));
  return acumulado;
}

function caminar(persona, camino) {
  pedirCuadro();
  // Sin WebGL o con movimiento reducido, el cambio es inmediato.
  if (reducido.matches || !dibujante) {
    Object.assign(persona, {x: camino.at(-1).x, z: camino.at(-1).z, giro: persona.lugar?.giro ?? 0, camino: null});
    if (persona.saliendo) quitar(persona);
    return;
  }
  persona.camino = camino;
  persona.tramos = largos(camino);
  persona.recorrido = 0;
  persona.velocidad = 6.5 + Math.random() * 1.5;
  persona.fase = Math.random() * 6;
  dejarEstela(camino);
}

function dejarEstela(camino) {
  const vertices = [];
  const indices = [];
  const ancho = .07;
  camino.forEach((p, i) => {
    const previo = camino[Math.max(i - 1, 0)];
    const siguiente = camino[Math.min(i + 1, camino.length - 1)];
    const dx = siguiente.x - previo.x;
    const dz = siguiente.z - previo.z;
    const largo = Math.hypot(dx, dz) || 1;
    vertices.push(p.x - dz / largo * ancho, .07, p.z + dx / largo * ancho, p.x + dz / largo * ancho, .07, p.z - dx / largo * ancho);
    if (i) indices.push(i * 2 - 2, i * 2 - 1, i * 2, i * 2 - 1, i * 2 + 1, i * 2);
  });
  const geometria = new T.BufferGeometry();
  geometria.setAttribute('position', new T.Float32BufferAttribute(vertices, 3));
  geometria.setIndex(indices);
  const estela = new T.Mesh(geometria, new T.MeshBasicMaterial({color: tema.estela, transparent: true, opacity: .75, depthWrite: false, side: T.DoubleSide}));
  estela.vida = 1;
  escena.add(estela);
  estelas.push(estela);
}

function quitar(persona) {
  persona.boton.remove();
  personas = personas.filter(p => p !== persona);
  if (seleccion === persona) elegir(null);
  actualizarPanel();
}

function crearBoton(persona) {
  const boton = document.createElement('button');
  boton.type = 'button';
  boton.className = 'persona';
  boton.setAttribute('aria-label', descripcion(persona));
  boton.addEventListener('click', evento => { evento.stopPropagation(); elegir(persona); });
  persona.boton = boton;
  capaPersonas.append(boton);
}
function descripcion(p) {
  return `Visita ${p.id}, ${p.zona}, ${p.minutos} minutos${p.simulada ? ', visita simulada' : ''}${p.porConciliar ? ', por conciliar' : ''}`;
}

function entrar(zona = NOMBRES[azar(5)]) {
  if (personas.filter(p => !p.saliendo).length >= datos.aforo_maximo) return;
  const persona = {id: siguienteId++, zona, simulada: Math.random() < .35, porConciliar: false, minutos: 0, x: PUERTA.x, z: PUERTA.z, giro: Math.PI};
  persona.lugar = lugarLibre(zona);
  personas.push(persona);
  crearBoton(persona);
  caminar(persona, ruta(PUERTA, null, persona.lugar, zona));
  brilloPuerta = 1;
  evento.textContent = `Entrada · visita ${persona.id} → ${zona}`;
  actualizarPanel();
}
function salir(persona) {
  persona.saliendo = true;
  caminar(persona, ruta({x: persona.x, z: persona.z}, persona.zona, PUERTA, null));
  brilloPuerta = 1;
  evento.textContent = `Salida · visita ${persona.id}`;
  actualizarPanel();
}
function cambiar(persona) {
  const desde = persona.zona;
  const opciones = NOMBRES.filter(n => n !== desde);
  persona.zona = opciones[azar(opciones.length)];
  persona.lugar = lugarLibre(persona.zona);
  caminar(persona, ruta({x: persona.x, z: persona.z}, desde, persona.lugar, persona.zona));
  evento.textContent = `Cambio de zona de la sede · visita ${persona.id} → ${persona.zona}`;
  actualizarPanel();
}
function quietas() {
  return personas.filter(p => !p.saliendo && !p.camino && !p.porConciliar);
}
function avanzar() {
  if (pausado) return;
  const hay = personas.filter(p => !p.saliendo).length;
  if (hay < objetivo) { entrar(); return; }
  const disponibles = quietas();
  if (hay > objetivo && disponibles.length) { salir(disponibles[azar(disponibles.length)]); return; }
  const tipo = turno++ % 3;
  if (!disponibles.length) return;
  if (tipo === 0) entrar();
  else if (tipo === 1) cambiar(disponibles[azar(disponibles.length)]);
  else salir(disponibles[azar(disponibles.length)]);
}
// Con ocupación lejos del objetivo llega gente de a varios; en régimen, un cambio cada 2 s.
function programar() {
  const hay = personas.filter(p => !p.saliendo).length;
  setTimeout(() => { avanzar(); programar(); }, Math.abs(hay - objetivo) > 1 ? 170 : 2000);
}

// --- Panel «Por zona» ---
const listaZonas = $('#zonas');
const filas = {};
for (const nombre of NOMBRES) {
  const fila = document.createElement('li');
  fila.innerHTML = `<button type="button" class="zona" aria-expanded="false"><span>${nombre}</span><span>0</span></button><div class="visitas" hidden></div>`;
  const boton = fila.querySelector('.zona');
  boton.addEventListener('click', () => abrirZona(zonaAbierta === nombre ? null : nombre));
  listaZonas.append(fila);
  filas[nombre] = {boton, cuenta: boton.lastElementChild, visitas: fila.querySelector('.visitas')};
}
function actualizarPanel() {
  const presentes = personas.filter(p => !p.saliendo);
  $('#total').textContent = presentes.length;
  $('#barra').style.width = `${presentes.length / datos.aforo_maximo * 100}%`;
  const sinEscena = document.documentElement.hasAttribute('data-sin-webgl');
  for (const nombre of NOMBRES) {
    const enZona = presentes.filter(p => p.zona === nombre);
    filas[nombre].cuenta.textContent = enZona.length;
    if (rotulos[nombre]) rotulos[nombre].lastElementChild.textContent = enZona.length;
    const abierta = sinEscena || zonaAbierta === nombre;
    filas[nombre].boton.setAttribute('aria-expanded', String(abierta));
    filas[nombre].visitas.hidden = !abierta;
    if (abierta) {
      const enfocada = document.activeElement?.dataset?.visita;
      filas[nombre].visitas.replaceChildren(...enZona.map(p => {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.dataset.visita = p.id;
        boton.setAttribute('aria-pressed', String(p === seleccion));
        boton.innerHTML = `<i class="marca ${p.porConciliar ? 'conciliar' : p.simulada ? 'simulada' : 'visita'}"></i>${p.id}`;
        boton.setAttribute('aria-label', descripcion(p));
        boton.addEventListener('click', () => elegir(p));
        return boton;
      }));
      if (enfocada) filas[nombre].visitas.querySelector(`[data-visita="${enfocada}"]`)?.focus();
    }
  }
}
// Zoom justo para que la zona entre en la escena, muros incluidos.
function encuadrar(s) {
  const x = (s.x0 + s.x1) / 2;
  const z = (s.z0 + s.z1) / 2;
  const derecha = new T.Vector3(0, 1, 0).cross(DIRECCION).normalize();
  const arriba = new T.Vector3().crossVectors(DIRECCION, derecha);
  let mitadAncho = 0;
  let mitadAlto = 0;
  for (const esquinaX of [s.x0, s.x1]) {
    for (const esquinaZ of [s.z0, s.z1]) {
      for (const y of [0, 3.4]) {
        const punto = new T.Vector3(esquinaX - x, y, esquinaZ - z);
        mitadAncho = Math.max(mitadAncho, Math.abs(punto.dot(derecha)));
        mitadAlto = Math.max(mitadAlto, Math.abs(punto.dot(arriba)));
      }
    }
  }
  const proporcion = ancho / alto;
  return {x, z, zoom: Math.min(mitadVista * proporcion / mitadAncho, mitadVista / mitadAlto) * .9};
}
function abrirZona(nombre) {
  zonaAbierta = nombre;
  const s = SALAS[nombre];
  contenedorEscena.toggleAttribute('data-acercada', Boolean(s));
  vista.destino = s ? encuadrar(s) : {x: .6, z: 1.2, zoom: 1};
  for (const [zona, rotulo] of Object.entries(rotulos)) rotulo.classList.toggle('apagado', Boolean(nombre) && zona !== nombre);
  actualizarPanel();
  pedirCuadro();
}
function elegir(persona) {
  seleccion = persona;
  tarjeta.hidden = !persona;
  if (persona) {
    tarjeta.innerHTML = `<b>Visita ${persona.id}</b>${persona.zona} · ${persona.minutos} min`
      + (persona.simulada ? ' · <span class="aviso-simulada">Visita simulada</span>' : '')
      + (persona.porConciliar ? ' · <span class="aviso-conciliar">Por conciliar</span>' : '');
  }
  actualizarPanel();
  pedirCuadro();
}
lienzo.addEventListener('click', () => elegir(null));
document.addEventListener('keydown', e => { if (e.key === 'Escape') elegir(null); });

// --- Rótulos anclados a la maqueta ---
const capaRotulos = $('#rotulos');
const rotulos = {};
const anclas = {
  'Musculación': [-10.5, 3.6, -13], 'Peso libre': [10, 3.6, -13],
  'Cardio': [-18, 3.6, 6.5], 'Funcional': [18, 1, 3], 'En la sede': [-.5, 3.6, -13],
};
for (const nombre of NOMBRES) {
  const r = document.createElement('span');
  r.className = 'rotulo';
  r.innerHTML = `${nombre}<b>0</b>`;
  capaRotulos.append(r);
  rotulos[nombre] = r;
}
const rotuloPuerta = document.createElement('span');
rotuloPuerta.className = 'rotulo puerta';
rotuloPuerta.textContent = 'Puerta';
capaRotulos.append(rotuloPuerta);

// --- Cámara y proyección ---
let ancho = 1;
let alto = 1;
let mitadVista = 30;
const proyectado = new T.Vector3();
function aPantalla(x, y, z, elemento) {
  proyectado.set(x, y, z).project(camara);
  elemento.style.left = `${(proyectado.x + 1) / 2 * ancho}px`;
  elemento.style.top = `${(1 - proyectado.y) / 2 * alto}px`;
}
function medir() {
  ancho = contenedorEscena.clientWidth;
  alto = contenedorEscena.clientHeight;
  if (!dibujante || !ancho || !alto) return;
  dibujante.setPixelRatio(Math.min(devicePixelRatio, 2));
  dibujante.setSize(ancho, alto, false);
  // Encuadre: la maqueta entra entera, dejando aire para el encabezado y los controles.
  const proporcion = ancho / alto;
  const anchoVisto = 52;
  const altoVisto = 46;
  mitadVista = Math.max(anchoVisto / 2 / proporcion, altoVisto / 2);
  camara.left = -mitadVista * proporcion;
  camara.right = mitadVista * proporcion;
  camara.top = mitadVista;
  camara.bottom = -mitadVista;
  if (zonaAbierta) abrirZona(zonaAbierta);
  pedirCuadro();
}
function ubicarCamara() {
  camara.zoom = vista.zoom;
  camara.position.set(vista.x + DIRECCION.x * 100, DIRECCION.y * 100, vista.z + DIRECCION.z * 100);
  camara.lookAt(vista.x, 0, vista.z);
  camara.updateProjectionMatrix();
  camara.updateMatrixWorld();
}

// --- Dibujo bajo demanda: sin trabajo por cuadro cuando nada se mueve ---
let cuadroPendiente = false;
let ultimo = 0;
let intervalos = [];
function pedirCuadro() {
  if (cuadroPendiente || !dibujante || document.hidden) return;
  cuadroPendiente = true;
  requestAnimationFrame(cuadro);
}
const ejeY = new T.Vector3(0, 1, 0);
const cuaternion = new T.Quaternion();
const matriz = new T.Matrix4();

function colocar(m, i, x, y, z, giro, inclinacion = 0) {
  auxiliar.position.set(x, y, z);
  auxiliar.rotation.set(inclinacion, giro, 0, 'YXZ');
  auxiliar.scale.setScalar(1);
  auxiliar.updateMatrix();
  m.setMatrixAt(i, auxiliar.matrix);
}
function moverPersonas(dt) {
  let moviendo = false;
  for (const p of [...personas]) {
    if (!p.camino) continue;
    moviendo = true;
    p.recorrido += p.velocidad * dt;
    const total = p.tramos.at(-1);
    // Frena al llegar para no clavarse en el lugar.
    const restante = total - p.recorrido;
    if (restante < 1.2) p.recorrido -= p.velocidad * dt * (1 - Math.max(.3, restante / 1.2));
    if (p.recorrido >= total - .02) {
      const fin = p.camino.at(-1);
      p.x = fin.x; p.z = fin.z; p.camino = null;
      if (p.saliendo) { quitar(p); continue; }
      continue;
    }
    let i = 1;
    while (p.tramos[i] < p.recorrido) i++;
    const t = (p.recorrido - p.tramos[i - 1]) / (p.tramos[i] - p.tramos[i - 1] || 1);
    const [a, b] = [p.camino[i - 1], p.camino[i]];
    p.x = a.x + (b.x - a.x) * t;
    p.z = a.z + (b.z - a.z) * t;
    const rumbo = Math.atan2(b.x - a.x, b.z - a.z);
    let delta = rumbo - p.giro;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    p.giro += delta * Math.min(1, dt * 11);
    p.fase += dt * 15;
  }
  // Al llegar, se orienta hacia su equipo.
  for (const p of personas) {
    if (p.camino || !p.lugar) continue;
    let delta = p.lugar.giro - p.giro;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    if (Math.abs(delta) > .01) { p.giro += delta * Math.min(1, dt * 7); moviendo = true; }
  }
  return moviendo;
}
function dibujarPersonas() {
  let redondas = 0;
  let conRombo = 0;
  let conAnillo = 0;
  personas.forEach((p, i) => {
    const tono = p.simulada ? tema.simulada : p.porConciliar ? tema.conciliar : tema.visita;
    const caminando = Boolean(p.camino);
    const paso = caminando ? Math.sin(p.fase) : 0;
    const rebote = caminando ? Math.abs(Math.cos(p.fase)) * .09 : 0;
    const inclinacion = caminando ? .13 : 0;
    colocar(torsos, i, p.x, 1.42 + rebote, p.z, p.giro, inclinacion);
    torsos.setColorAt(i, color.set(tono).multiplyScalar(tema.brilloFigura));
    const lx = Math.cos(p.giro) * .14;
    const lz = -Math.sin(p.giro) * .14;
    colocar(piernas, i * 2, p.x - lx, .47 + rebote * .5, p.z - lz, p.giro, paso * .55);
    colocar(piernas, i * 2 + 1, p.x + lx, .47 + rebote * .5, p.z + lz, p.giro, -paso * .55);
    color.set(tono).multiplyScalar(tema.brilloFigura * .62);
    piernas.setColorAt(i * 2, color);
    piernas.setColorAt(i * 2 + 1, color);
    if (p.simulada) {
      colocar(rombos, conRombo, p.x, 2.36 + rebote, p.z, p.giro);
      rombos.setColorAt(conRombo++, color.set(tono).multiplyScalar(tema.brilloFigura));
    } else {
      colocar(cabezas, redondas, p.x, 2.26 + rebote, p.z, p.giro);
      cabezas.setColorAt(redondas++, color.set(tono).multiplyScalar(tema.brilloFigura));
    }
    if (p.porConciliar) {
      colocar(anillos, conAnillo, p.x, .09, p.z, 0);
      anillos.setColorAt(conAnillo++, color.set(tema.conciliar));
    }
    aPantalla(p.x, 1.4, p.z, p.boton);
  });
  torsos.count = personas.length;
  piernas.count = personas.length * 2;
  cabezas.count = redondas;
  rombos.count = conRombo;
  anillos.count = conAnillo;
  for (const m of [torsos, piernas, cabezas, rombos, anillos]) {
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }
  seleccionado.visible = Boolean(seleccion);
  if (seleccion) {
    seleccionado.position.set(seleccion.x, .1, seleccion.z);
    aPantalla(seleccion.x, 2.6, seleccion.z, tarjeta);
    const mitad = tarjeta.offsetWidth / 2 + 8;
    tarjeta.style.left = `${Math.min(ancho - mitad, Math.max(mitad, parseFloat(tarjeta.style.left)))}px`;
  }
}
function cuadro(ahora) {
  cuadroPendiente = false;
  const dt = Math.min(.05, (ahora - ultimo) / 1000 || .016);
  if (ultimo && ahora - ultimo < 200) intervalos.push({ahora, ms: ahora - ultimo});
  ultimo = ahora;

  let seguir = moverPersonas(dt);

  for (let i = estelas.length - 1; i >= 0; i--) {
    const e = estelas[i];
    e.vida -= dt / 2.6;
    e.material.opacity = Math.max(0, e.vida) * .75;
    if (e.vida <= 0) {
      escena.remove(e); e.geometry.dispose(); e.material.dispose(); estelas.splice(i, 1);
    } else seguir = true;
  }

  for (const nombre of NOMBRES) {
    const f = focos[nombre];
    const cuantos = personas.filter(p => p.zona === nombre && !p.saliendo).length;
    const meta = tema.focoBase + tema.focoPorVisita * cuantos;
    f.actual += (meta - f.actual) * Math.min(1, dt * (reducido.matches ? 60 : 2.5));
    f.luz.intensity = f.actual;
    if (Math.abs(meta - f.actual) > 1) seguir = true;
  }

  brilloPuerta = Math.max(0, brilloPuerta - dt * 1.3);
  halo.material.opacity = (tema === TEMAS.noche ? .28 : .05) + brilloPuerta * .5;
  if (brilloPuerta > 0) seguir = true;

  if (vista.destino) {
    const k = reducido.matches ? 1 : Math.min(1, dt * 4.5);
    vista.x += (vista.destino.x - vista.x) * k;
    vista.z += (vista.destino.z - vista.z) * k;
    vista.zoom += (vista.destino.zoom - vista.zoom) * k;
    if (Math.abs(vista.destino.zoom - vista.zoom) < .002 && Math.hypot(vista.destino.x - vista.x, vista.destino.z - vista.z) < .01) {
      Object.assign(vista, vista.destino); vista.destino = null;
    } else seguir = true;
  }
  ubicarCamara();
  for (const nombre of NOMBRES) aPantalla(...anclas[nombre], rotulos[nombre]);
  aPantalla(PUERTA.x, 0, 17.5, rotuloPuerta);
  dibujarPersonas();
  dibujante.render(escena, camara);
  dibujados++;
  medirFps(ahora);
  if (seguir) pedirCuadro();
  else ultimo = 0;
}

let dibujados = 0;
let ultimaMedicion = 0;
let medicion = {promedio: 0, percentil_5: 0, cuadros: 0};
function medirFps(ahora) {
  intervalos = intervalos.filter(c => c.ahora >= ahora - 10000);
  if (ahora - ultimaMedicion < 500 || !intervalos.length) return;
  ultimaMedicion = ahora;
  const ordenados = intervalos.map(c => 1000 / c.ms).sort((a, b) => a - b);
  medicion = {
    promedio: 1000 * intervalos.length / intervalos.reduce((n, c) => n + c.ms, 0),
    percentil_5: ordenados[Math.floor(ordenados.length * .05)],
    cuadros: intervalos.length,
  };
  $('#fps').textContent = `${medicion.promedio.toFixed(0)} fps en movimiento · p5 ${medicion.percentil_5.toFixed(0)} · ${personas.length} visitas`;
}

// --- Luz ---
function aplicarLuz(nombre) {
  tema = TEMAS[nombre];
  document.documentElement.dataset.luz = nombre;
  $('#luz').textContent = nombre === 'noche' ? 'Ver de día' : 'Ver de noche';
  hemisferio.color.set(tema.hemisferio[0]);
  hemisferio.groundColor.set(tema.hemisferio[1]);
  hemisferio.intensity = tema.hemisferio[2];
  sol.color.set(tema.sol[0]);
  sol.intensity = tema.sol[1];
  relleno.intensity = tema.relleno;
  materialVentana.emissiveIntensity = tema.ventana;
  if (dibujante) dibujante.toneMappingExposure = tema.exposicion;
  pedirCuadro();
}

// --- Controles ---
for (const boton of document.querySelectorAll('[data-objetivo]')) {
  boton.addEventListener('click', () => {
    objetivo = Number(boton.dataset.objetivo);
    document.querySelectorAll('[data-objetivo]').forEach(b => b.setAttribute('aria-pressed', String(b === boton)));
  });
}
$('#luz').addEventListener('click', () => aplicarLuz(tema === TEMAS.noche ? 'dia' : 'noche'));
$('#pausa').addEventListener('click', () => {
  pausado = !pausado;
  $('#pausa').textContent = pausado ? 'Seguir' : 'Pausar';
});

// --- Arranque ---
const POR_CONCILIAR = new Set([6, 23]);
if (dibujante) {
  dibujante.shadowMap.enabled = true;
  dibujante.shadowMap.type = T.PCFSoftShadowMap;
  dibujante.toneMapping = T.ACESFilmicToneMapping;
  dibujante.outputColorSpace = T.SRGBColorSpace;
}
$('#aforo').textContent = datos.aforo_maximo;
for (const dato of datos.personas) {
  const persona = {...dato, porConciliar: POR_CONCILIAR.has(dato.id), giro: 0};
  persona.lugar = lugarLibre(persona.zona);
  persona.x = persona.lugar.x;
  persona.z = persona.lugar.z;
  persona.giro = persona.lugar.giro;
  personas.push(persona);
  crearBoton(persona);
}
aplicarLuz('noche');
actualizarPanel();
evento.textContent = 'Puerta abierta · un cambio cada 2 s';
new ResizeObserver(medir).observe(contenedorEscena);
medir();
document.addEventListener('visibilitychange', () => {
  ultimo = 0;
  intervalos = [];
  if (!document.hidden) pedirCuadro();
});
programar();
window.maqueta = {get personas() { return personas; }, get fps() { return medicion; }, get dibujados() { return dibujados; }, abrirZona, entrar, avanzar, elegir, aplicarLuz};
