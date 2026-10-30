// Piezas de papel de la referencia aprobada en #153.
import * as T from 'three';
import {CARRIL, SALAS, NOMBRES} from './escena-ocupacion-plano.js';
export function construirMaqueta(escena) {
  const papel50 = '#fbf7f0', papel100 = '#f3ecdf', papel200 = '#e6dccb';
  const papel400 = '#c9bfae', tinta400 = '#8f8270', tinta600 = '#5c554a';
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


  return {lugares, materialVentana};
}
