// Prototipo descartable #81: comparación visual, sin datos de la aplicación.
import * as THREE from 'three';

export const zonas = ['pecho', 'espalda_alta', 'dorsales', 'hombros', 'biceps', 'triceps', 'abdomen', 'gluteos', 'cuadriceps', 'isquiotibiales', 'pantorrillas', 'zona_lumbar', 'rodillas', 'cuello'];
const nombres = ['Pecho', 'Espalda alta', 'Dorsales', 'Hombros', 'Bíceps', 'Tríceps', 'Abdomen', 'Glúteos', 'Cuádriceps', 'Isquiotibiales', 'Pantorrillas', 'Zona lumbar', 'Rodillas', 'Cuello'];
const estados = Object.fromEntries(zonas.map(z => [z, 'sin_marcar']));
estados.pecho = 'trabajada'; estados.cuadriceps = 'trabajada'; estados.rodillas = 'con_dolor';
const colores = {sin_marcar: '#c9bfae', trabajada: '#1f5a43', con_dolor: '#b2452a'};
const materiales = zonas.map(z => new THREE.MeshStandardMaterial({color: colores[estados[z]], roughness: 0.8, side: THREE.DoubleSide}));
const neutro = new THREE.MeshStandardMaterial({color: '#c9bfae', roughness: 0.8});
const escena = new THREE.Scene();
const cuerpo = new THREE.Group(); escena.add(cuerpo);
const camara = new THREE.PerspectiveCamera(36, 1, 0.01, 30); camara.position.set(0, 1, 3.8); camara.lookAt(0, 0.9, 0);
const lienzo = document.querySelector('canvas');
const dibujante = new THREE.WebGLRenderer({canvas: lienzo, antialias: true});
dibujante.setPixelRatio(Math.min(devicePixelRatio, 2));
dibujante.setClearColor('#f3ecdf');
escena.add(new THREE.HemisphereLight(0xffffff, 0x5c554a, 2.8));
const luz = new THREE.DirectionalLight(0xffffff, 3); luz.position.set(2, 3, 4); escena.add(luz);
const superficies = [];
let seleccion = 'pecho';
function emitir(zona) {
  seleccion = zona;
  document.querySelector('output').textContent = `${zona} · ${estados[zona]}`;
  document.querySelectorAll('[data-zona]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.zona === zona)));
  document.querySelector('#estado').value = estados[zona];
  window.dispatchEvent(new CustomEvent('zona-seleccionada', {detail: {zona}}));
}
zonas.forEach((zona, i) => {
  const boton = document.createElement('button'); boton.textContent = nombres[i]; boton.dataset.zona = zona;
  boton.addEventListener('click', () => emitir(zona)); document.querySelector('#zonas').append(boton);
});
document.querySelector('#estado').addEventListener('change', e => {
  estados[seleccion] = e.target.value;
  materiales[zonas.indexOf(seleccion)].color.set(colores[e.target.value]); emitir(seleccion);
});
emitir(seleccion);

// El modelo está en pose T, metros, frente +Z. Cada triángulo se asigna
// por su centro en la geometría original; no es segmentación anatómica clínica.
export function zonaDelPunto(x, y, z) {
  const lateral = Math.abs(x);
  if (y > 1.6) return -1;
  if (y > 1.48 && lateral < 0.12) return 13;
  if (lateral > 0.23 && y > 1.25) {
    if (lateral < 0.36) return 3;
    if (lateral < 0.64) return z >= -0.08 ? 4 : 5;
    return -1;
  }
  if (y > 1.28) return z >= 0 ? 0 : 1;
  if (y > 1.05) return z >= 0 ? 6 : (lateral > 0.11 ? 2 : 11);
  if (y > 0.83) return z >= 0 ? 6 : 7;
  if (y > 0.57) return z >= 0 ? 8 : 9;
  if (y > 0.43) return 12;
  return 10;
}
async function cargarModelo() {
  const {GLTFLoader} = await import('../../gimnasio/static/vendor/three@0.186.0/loaders/GLTFLoader.js');
  const gltf = await new GLTFLoader().loadAsync('../recursos/cuerpo.glb');
  gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse(objeto => {
    if (!objeto.isMesh) return;
    const geometria = objeto.geometry.index ? objeto.geometry.toNonIndexed() : objeto.geometry.clone();
    geometria.applyMatrix4(objeto.matrixWorld);
    const posiciones = geometria.attributes.position;
    geometria.clearGroups();
    for (let i = 0; i < posiciones.count; i += 3) {
      const centro = new THREE.Vector3();
      for (let j = 0; j < 3; j++) centro.add(new THREE.Vector3().fromBufferAttribute(posiciones, i + j));
      centro.divideScalar(3);
      const zona = zonaDelPunto(centro.x, centro.y, centro.z);
      geometria.addGroup(i, 3, zona < 0 ? 14 : zona);
    }
    // Ordenar índices por zona: como máximo quince llamadas por malla.
    const indices = Array.from({length: 15}, () => []);
    for (const grupo of geometria.groups) {
      indices[grupo.materialIndex].push(grupo.start, grupo.start + 1, grupo.start + 2);
    }
    geometria.clearGroups();
    const ordenados = [];
    indices.forEach((lista, zona) => {
      if (lista.length) geometria.addGroup(ordenados.length, lista.length, zona);
      ordenados.push(...lista);
    });
    geometria.setIndex(ordenados);
    const malla = new THREE.Mesh(geometria, [...materiales, neutro]);
    cuerpo.add(malla); superficies.push(malla);
  });
}
function crearEstilizado() {
  function pieza(zona, x, y, z, ancho, alto, fondo) {
    const malla = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16), zona < 0 ? neutro : materiales[zona]);
    malla.position.set(x, y, z); malla.scale.set(ancho, alto, fondo); malla.userData.zona = zona;
    cuerpo.add(malla); superficies.push(malla);
  }
  pieza(-1, 0, 1.67, 0, .115, .15, .105); pieza(13, 0, 1.48, 0, .065, .09, .065);
  pieza(0, 0, 1.31, .055, .235, .16, .085); pieza(1, 0, 1.34, -.065, .22, .13, .07);
  pieza(6, 0, 1.08, .035, .16, .15, .09); pieza(11, 0, 1.08, -.065, .14, .12, .055);
  for (const lado of [-1, 1]) {
    pieza(2, lado*.165, 1.2, -.06, .075, .12, .065);
    pieza(3, lado*.27, 1.37, 0, .09, .10, .09);
    pieza(4, lado*.34, 1.21, .045, .065, .13, .055); pieza(5, lado*.34, 1.21, -.045, .065, .13, .055);
    pieza(-1, lado*.38, .99, 0, .052, .14, .05); pieza(-1, lado*.40, .83, 0, .05, .07, .035);
    pieza(7, lado*.10, .88, -.04, .11, .13, .10);
    pieza(8, lado*.115, .69, .04, .09, .18, .08); pieza(9, lado*.115, .69, -.055, .085, .18, .07);
    pieza(12, lado*.115, .48, .025, .067, .065, .065); pieza(10, lado*.115, .28, -.015, .065, .16, .065);
    pieza(-1, lado*.115, .08, .04, .065, .055, .12);
  }
}
let arrastre = null;
lienzo.addEventListener('pointerdown', e => {arrastre = {x: e.clientX, inicio: e.clientX, y: e.clientY}; lienzo.setPointerCapture(e.pointerId);});
lienzo.addEventListener('pointermove', e => {if (arrastre) {cuerpo.rotation.y += (e.clientX-arrastre.x)*.012; arrastre.x=e.clientX;}});
lienzo.addEventListener('pointerup', e => {
  if (arrastre && Math.hypot(e.clientX-arrastre.inicio, e.clientY-arrastre.y) < 5) {
    const rect = lienzo.getBoundingClientRect(); const rayo = new THREE.Raycaster();
    rayo.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1, -(e.clientY-rect.top)/rect.height*2+1), camara);
    const impacto = rayo.intersectObjects(superficies)[0];
    if (impacto) {const i = impacto.object.userData.zona ?? impacto.face.materialIndex; if (i >= 0 && i < 14) emitir(zonas[i]);}
  }
  arrastre = null;
});
lienzo.addEventListener('pointercancel', () => {arrastre = null;});
document.querySelector('#girar').addEventListener('input', e => {cuerpo.rotation.y = Number(e.target.value)*Math.PI/180;});
document.querySelector('#frente').addEventListener('click', () => {cuerpo.rotation.y = 0; document.querySelector('#girar').value = 0;});
function ajustar() {const {width, height} = lienzo.getBoundingClientRect(); dibujante.setSize(width, height, false); camara.aspect = width/height; camara.updateProjectionMatrix();}
const ajuste = new ResizeObserver(ajustar); ajuste.observe(lienzo);
window.prototipo = {estados, zonas, cuerpo, dibujante, listo: false, cuadros: []};
try {
  if (document.body.dataset.modelo === 'a') await cargarModelo(); else crearEstilizado();
  ajustar();
  await new Promise(requestAnimationFrame);
  dibujante.render(escena, camara);
  window.prototipo.primerCuadro = performance.now(); window.prototipo.listo = true;
  document.querySelector('#carga').textContent = 'Arrastrá para rotar o tocá una zona del cuerpo.';
  function cuadro(tiempo) {window.prototipo.cuadros.push(tiempo); if (window.prototipo.cuadros.length > 1200) window.prototipo.cuadros.shift(); dibujante.render(escena, camara); requestAnimationFrame(cuadro);}
  requestAnimationFrame(cuadro);
} catch (error) {document.querySelector('#carga').textContent = 'No se pudo cargar el cuerpo 3D.'; console.error(error);}
