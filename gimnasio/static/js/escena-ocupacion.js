// Maqueta de papel: dibujo bajo demanda y datos provistos por recepcion.
import * as T from 'three';
import {construirMaqueta} from './escena-ocupacion-maqueta.js';
import {CARRIL, PUERTA, SALAS, NOMBRES} from './escena-ocupacion-plano.js';
import {diferenciarVisitas, esDibujoPorSoftware} from './escena-ocupacion-estado.js';

function nombreDelRenderizador() {
  const contexto = document.createElement('canvas').getContext('webgl2');
  const extension = contexto?.getExtension('WEBGL_debug_renderer_info');
  const nombre = extension ? contexto.getParameter(extension.UNMASKED_RENDERER_WEBGL) : '';
  contexto?.getExtension('WEBGL_lose_context')?.loseContext();
  return nombre;
}

export function crearEscena(contenedorEscena, alElegir) {
  const token = nombre => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
  const lienzo = contenedorEscena.querySelector('canvas');
  const capaPersonas = contenedorEscena.querySelector('[data-puntos]');
  const tarjeta = contenedorEscena.querySelector('[data-rotulo-visita]');
  const porSoftware = esDibujoPorSoftware(nombreDelRenderizador());
  const dibujante = new T.WebGLRenderer({canvas: lienzo, antialias: !porSoftware, alpha: true});
  const escena = new T.Scene();
  const camara = new T.OrthographicCamera(-1, 1, 1, -1, .1, 400);
  const DIRECCION = new T.Vector3(1, 1.02, 1).normalize();
  const vista = {x: .6, z: 1.2, zoom: 1, destino: null};
  const reducido = matchMedia('(prefers-reduced-motion: reduce)');
  const oscuro = matchMedia('(prefers-color-scheme: dark)');
  const {lugares, materialVentana} = construirMaqueta(escena);
  const auxiliar = new T.Object3D();
  const color = new T.Color();
  let personas = [], anteriores = [], seleccion = null, zonaAbierta = null;
  let inicial = true, tema;
  const estelas = [];
  const anclas = {'Musculación': [-10.5, 3.6, -13], 'Peso libre': [10, 3.6, -13],
    'Cardio': [-18, 3.6, 6.5], 'Funcional': [18, 1, 3], 'En la sede': [-.5, 3.6, -13], 'Puerta': [PUERTA.x, 0, 17.5]};
  const rotulos = Object.fromEntries(Object.keys(anclas).map(nombre => {
    const rotulo = document.createElement('span');
    rotulo.className = 'rotulo-zona-escena';
    rotulo.textContent = nombre;
    contenedorEscena.append(rotulo);
    return [nombre, rotulo];
  }));
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
  let capacidad = 96;
  const materialFigura = new T.MeshStandardMaterial({roughness: .55});
  const malla = (geometria, n = capacidad) => {
    const m = new T.InstancedMesh(geometria, materialFigura, n);
    m.castShadow = true;
    m.frustumCulled = false;
    m.setColorAt(0, color.set('#fff'));
    escena.add(m);
    return m;
  };
  let torsos = malla(new T.CapsuleGeometry(.27, .62, 4, 10));
  let piernas = malla(new T.CapsuleGeometry(.1, .62, 3, 6), capacidad * 2);
  let cabezas = malla(new T.SphereGeometry(.23, 14, 10));
  let rombos = malla(new T.OctahedronGeometry(.31));
  let anillos = new T.InstancedMesh(new T.RingGeometry(.52, .68, 28).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({transparent: true}), capacidad);
  anillos.frustumCulled = false;
  anillos.setColorAt(0, color.set('#fff'));
  escena.add(anillos);
  const seleccionado = new T.Mesh(new T.RingGeometry(.66, .98, 36).rotateX(-Math.PI / 2), new T.MeshBasicMaterial({color: token('--texto'), depthTest: false, transparent: true, toneMapped: false}));
  seleccionado.visible = false;
  seleccionado.renderOrder = 5;
  escena.add(seleccionado);

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
    dibujante.setPixelRatio(porSoftware ? 1 : Math.min(devicePixelRatio, 2));
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
    if (zonaAbierta) vista.destino = encuadrar(SALAS[zonaAbierta]);
    pedirCuadro();
  }
  function ubicarCamara() {
    camara.zoom = vista.zoom;
    camara.position.set(vista.x + DIRECCION.x * 100, DIRECCION.y * 100, vista.z + DIRECCION.z * 100);
    camara.lookAt(vista.x, 0, vista.z);
    camara.updateProjectionMatrix();
    camara.updateMatrixWorld();
  }

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
        p.zonaFisica = p.zonaDestino;
        continuar(p);
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
      if (reducido.matches) { p.giro = p.lugar.giro; continue; }
      let delta = p.lugar.giro - p.giro;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      if (Math.abs(delta) > .01) { p.giro += delta * Math.min(1, dt * 7); moviendo = true; }
    }
    return moviendo;
  }
  function dibujarPersonas() {
    if (personas.length > capacidad) {
      capacidad = Math.max(personas.length, capacidad * 2);
      const ampliar = (anterior, cantidad) => {
        const nueva = new T.InstancedMesh(anterior.geometry, anterior.material, cantidad);
        nueva.castShadow = anterior.castShadow;
        nueva.frustumCulled = false;
        nueva.setColorAt(0, color.set('#fff'));
        escena.remove(anterior);
        anterior.dispose();
        escena.add(nueva);
        return nueva;
      };
      torsos = ampliar(torsos, capacidad);
      piernas = ampliar(piernas, capacidad * 2);
      cabezas = ampliar(cabezas, capacidad);
      rombos = ampliar(rombos, capacidad);
      anillos = ampliar(anillos, capacidad);
    }
    let redondas = 0;
    let conRombo = 0;
    let conAnillo = 0;
    personas.forEach((p, i) => {
      const tono = p.simulada ? tema.simulada : p.por_conciliar ? tema.conciliar : tema.visita;
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
      if (p.por_conciliar) {
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
      const mitad = Math.min(ancho / 2, tarjeta.offsetWidth / 2 + 8);
      tarjeta.style.left = `${Math.min(ancho - mitad, Math.max(mitad, parseFloat(tarjeta.style.left)))}px`;
    }
  }
  // Las rutas en curso terminan en su puerta antes de atender otro destino.
  function continuar(p) {
    if (p.camino) return;
    if (!p.retirar && p.zonaFisica === p.zona && p.lugar) return;
    p.saliendo = p.retirar;
    const desde = p.zonaFisica;
    const hasta = p.saliendo ? null : p.zona;
    if (hasta) p.lugar = lugarLibre(hasta, p);
    p.zonaDestino = hasta;
    caminar(p, ruta({x: p.x, z: p.z}, desde, p.saliendo ? PUERTA : p.lugar, hasta));
  }
  function lugarLibre(zona, persona) {
    const usados = personas.filter(p => p !== persona && !p.retirar && p.lugar).map(p => p.lugar);
    const disponible = lugar => !usados.some(usado => usado.x === lugar.x && usado.z === lugar.z);
    const libre = lugares[zona].find(disponible);
    if (libre) return libre;
    const sala = SALAS[zona];
    // Buscar también entre los lugares alternativos ya asignados. Si se llena
    // la sala, refinar la distribución sin salir de sus límites.
    for (let paso = 1.5; ; paso /= 2) {
      for (let z = sala.z0 + 1; z < sala.z1 - 1; z += paso) {
        for (let x = sala.x0 + 1; x < sala.x1 - 1; x += paso) {
          const lugar = {x, z, giro: 0};
          if (disponible(lugar)) return lugar;
        }
      }
    }
  }

  function quitar(p) {
    p.boton.remove();
    personas = personas.filter(persona => persona !== p);
    if (seleccion === p) { seleccion = null; tarjeta.hidden = true; }
  }
  function caminar(p, camino) {
    if (reducido.matches) {
      Object.assign(p, {x: camino.at(-1).x, z: camino.at(-1).z, camino: null, zonaFisica: p.zonaDestino});
      if (p.saliendo) quitar(p);
      return;
    }
    Object.assign(p, {camino, tramos: largos(camino), recorrido: 0, velocidad: 7, fase: 0});
    const geometria = new T.BufferGeometry().setFromPoints(camino.map(punto => new T.Vector3(punto.x, .08, punto.z)));
    const estela = new T.Line(geometria, new T.LineBasicMaterial({color: tema.estela, transparent: true, opacity: .7}));
    estela.vida = 2.6;
    estelas.push(estela);
    escena.add(estela);
  }
  function descripcion(p) {
    return `${p.zona} · ${p.minutos} min${p.simulada ? ' · Visita simulada' : ''}${p.por_conciliar ? ' · Por conciliar' : ''}`;
  }
  function elegir(p) {
    seleccion = p;
    tarjeta.textContent = `${p.nombre} · ${descripcion(p)}`;
    tarjeta.hidden = false;
    for (const persona of personas) persona.boton.setAttribute('aria-pressed', String(persona === p));
    pedirCuadro();
    alElegir(p);
  }
  function actualizar(visitas) {
    // La API entrega claves de zona de la sede. Los nombres salen del bloque Por zona.
    const nombres = Object.fromEntries([...document.querySelectorAll('[data-zona-sede]')]
      .map(fila => [fila.dataset.zonaSede, fila.querySelector('progress').getAttribute('aria-label')]));
    const actuales = visitas.map(p => ({...p, zona: SALAS[nombres[p.zona]] ? nombres[p.zona] : 'En la sede'}));
    if (!inicial && JSON.stringify(anteriores) === JSON.stringify(actuales)) return;
    const diferencias = diferenciarVisitas(anteriores, actuales);
    for (const dato of diferencias.entradas) {
      let p = personas.find(persona => persona.id === dato.id);
      if (p) { p.retirar = false; continue; }
      p = {...dato, x: PUERTA.x, z: PUERTA.z, giro: 0, zonaFisica: null, retirar: false};
      p.lugar = lugarLibre(p.zona, p);
      p.boton = document.createElement('button');
      p.boton.type = 'button';
      p.boton.className = 'punto-visita';
      p.boton.dataset.puntoVisita = p.id;
      p.boton.addEventListener('click', () => elegir(p));
      capaPersonas.append(p.boton);
      personas.push(p);
      if (inicial) Object.assign(p, p.lugar, {zonaFisica: p.zona});
      else { continuar(p); brilloPuerta = reducido.matches ? 0 : 1; }
    }
    for (const dato of actuales) {
      const p = personas.find(persona => persona.id === dato.id);
      Object.assign(p, dato);
      p.boton.setAttribute('aria-label', `Visita ${actuales.indexOf(dato) + 1} · ${descripcion(p)}`);
      p.boton.dataset.simulada = String(p.simulada);
      p.boton.dataset.porConciliar = String(p.por_conciliar);
    }
    for (const dato of diferencias.cambios) continuar(personas.find(p => p.id === dato.id));
    for (const dato of diferencias.salidas) {
      const p = personas.find(persona => persona.id === dato.id);
      if (p) {
        p.retirar = true;
        p.boton.disabled = true;
        continuar(p);
        brilloPuerta = reducido.matches ? 0 : 1;
      }
    }
    anteriores = actuales;
    inicial = false;
    if (seleccion && !seleccion.retirar) tarjeta.textContent = `${seleccion.nombre} · ${descripcion(seleccion)}`;
    pedirCuadro();
  }

  let cuadroPendiente = 0, ultimo = 0, yaDibujo = false, sombreadoresListos = false;
  function pedirCuadro() {
    if (!cuadroPendiente && !document.hidden) cuadroPendiente = requestAnimationFrame(cuadro);
  }
  function cuadro(ahora) {
    cuadroPendiente = 0;
    if (document.hidden) { ultimo = 0; return; }
    const dt = Math.min(.05, (ahora - ultimo) / 1000 || .016);
    ultimo = ahora;
    let seguir = moverPersonas(dt);
    for (const e of [...estelas]) {
      e.vida -= dt;
      e.material.opacity = Math.max(0, e.vida / 2.6) * .7;
      if (e.vida <= 0 || reducido.matches) {
        escena.remove(e); e.geometry.dispose(); e.material.dispose(); estelas.splice(estelas.indexOf(e), 1);
      } else seguir = true;
    }
    for (const nombre of NOMBRES) {
      const f = focos[nombre];
      const cuantos = personas.filter(p => p.zona === nombre && !p.retirar).length;
      rotulos[nombre].textContent = `${nombre} ${cuantos}`;
      const meta = tema.focoBase + tema.focoPorVisita * cuantos;
      // La luz solo se anima con un cambio de ocupación, no al abrir la pantalla.
      f.actual += (meta - f.actual) * (reducido.matches || !yaDibujo ? 1 : Math.min(1, dt * 2.5));
      f.luz.intensity = f.actual;
      if (Math.abs(meta - f.actual) > 1) seguir = true;
    }
    brilloPuerta = Math.max(0, brilloPuerta - dt * 1.3);
    halo.material.opacity = (oscuro.matches ? .28 : .05) + brilloPuerta * .5;
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
    for (const [nombre, ancla] of Object.entries(anclas)) aPantalla(...ancla, rotulos[nombre]);
    dibujarPersonas();
    if (sombreadoresListos) {
      dibujante.render(escena, camara);
      yaDibujo = true;
    }
    if (seguir) pedirCuadro();
    else ultimo = 0;
  }
  function aplicarLuz() {
    const noche = oscuro.matches;
    tema = {visita: token('--exito'), simulada: token('--acento'), conciliar: token('--alerta'),
      estela: token('--texto-suave'), brilloFigura: noche ? 1.7 : 1, focoBase: noche ? 250 : 0, focoPorVisita: noche ? 18 : 9};
    hemisferio.color.set(noche ? '#6b6470' : '#fffdf9');
    hemisferio.groundColor.set(noche ? '#1e1b16' : '#c9bfae');
    hemisferio.intensity = noche ? .8 : 1.75;
    sol.color.set(noche ? '#b9c0d2' : '#fff0da');
    sol.intensity = noche ? .55 : 3.1;
    relleno.intensity = noche ? 1.1 : .5;
    materialVentana.emissiveIntensity = noche ? 2.4 : 0;
    dibujante.toneMappingExposure = noche ? 1 : .95;
    pedirCuadro();
  }
  function abrirZona(nombre) {
    zonaAbierta = SALAS[nombre] ? nombre : null;
    vista.destino = zonaAbierta ? encuadrar(SALAS[nombre]) : {x: .6, z: 1.2, zoom: 1};
    pedirCuadro();
  }
  function inmovilizar() {
    if (reducido.matches) {
      for (const p of [...personas]) {
        if (p.retirar) { quitar(p); continue; }
        p.camino = null; p.zonaFisica = p.zona;
        p.lugar = lugarLibre(p.zona, p);
        Object.assign(p, p.lugar);
      }
      brilloPuerta = 0;
    }
    pedirCuadro();
  }
  dibujante.shadowMap.enabled = !porSoftware;
  dibujante.shadowMap.type = T.PCFSoftShadowMap;
  dibujante.toneMapping = T.ACESFilmicToneMapping;
  dibujante.outputColorSpace = T.SRGBColorSpace;
  new ResizeObserver(medir).observe(contenedorEscena);
  document.addEventListener('visibilitychange', () => {
    cancelAnimationFrame(cuadroPendiente); cuadroPendiente = 0; ultimo = 0;
    if (!document.hidden) pedirCuadro();
  });
  oscuro.addEventListener('change', aplicarLuz);
  reducido.addEventListener('change', inmovilizar);
  aplicarLuz();
  medir();
  // Compilar en segundo plano: sin GPU, hacerlo al dibujar congela la pantalla varios segundos.
  dibujante.compileAsync(escena, camara).catch(() => {}).finally(() => {
    sombreadoresListos = true;
    pedirCuadro();
  });
  return {actualizar, abrirZona, elegirVisita(id) {
    const persona = personas.find(p => p.id === id && !p.retirar);
    if (persona) elegir(persona);
  }};
}
