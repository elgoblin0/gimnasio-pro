import * as THREE from "three";
import { ZONAS_CUERPO } from "./zonas.js";
import { separarRotulos } from "./volumen-zonas.js";

// Cada zona es una o más elipses sobre el cuerpo en reposo (brazos en cruz), espejadas en x.
// lado: 1 frente, -1 espalda, 0 ambos; corte: plano z que separa frente y espalda.
const aParches = filas => filas.map(([zona, x, y, rx, ry, lado, corte]) => ({zona: ZONAS_CUERPO.findIndex(z => z.id === zona), x, y, rx, ry, lado, corte}));

// Cada figura trae los brazos bajos: pivote y caída los llevan a la cruz; axila separa brazo y torso.
const FIGURAS = {
  masculina: {
    modelo: "masculina.glb",
    pivote: {x: .2, y: 1.42}, caida: 1.19, axila: {x: .175, y: 1.27, pendiente: .397},
    parches: aParches([
      ["pecho", .085, 1.37, .105, .08, 1, 0],
      ["espalda_alta", .085, 1.385, .13, .095, -1, 0],
      ["dorsales", .115, 1.195, .06, .115, -1, 0],
      ["hombros", .225, 1.445, .07, .07, 0, 0],
      ["biceps", .36, 1.405, .13, .06, 1, 0],
      ["triceps", .36, 1.405, .13, .06, -1, 0],
      ["abdomen", 0, 1.11, .105, .16, 1, 0],
      ["gluteos", .085, .91, .095, .085, -1, 0],
      ["cuadriceps", .115, .68, .08, .125, 1, 0],
      ["isquiotibiales", .12, .67, .075, .115, -1, 0],
      ["pantorrillas", .165, .325, .055, .105, -1, -.05],
      ["zona_lumbar", 0, 1.06, .055, .085, -1, 0],
      ["rodillas", .135, .515, .06, .055, 0, 0],
      ["cuello", 0, 1.515, .06, .042, 0, 0],
    ]),
  },
  femenina: {
    modelo: "femenina.glb",
    pivote: {x: .16, y: 1.42}, caida: 1.18, axila: {x: .155, y: 1.27, pendiente: .405},
    parches: aParches([
      ["pecho", .075, 1.33, .095, .085, 1, 0],
      ["espalda_alta", .08, 1.385, .115, .095, -1, 0],
      ["dorsales", .095, 1.2, .05, .105, -1, 0],
      ["hombros", .19, 1.44, .065, .07, 0, 0],
      ["biceps", .31, 1.41, .125, .05, 1, -.03],
      ["triceps", .31, 1.41, .125, .05, -1, -.03],
      ["abdomen", 0, 1.08, .095, .15, 1, 0],
      ["gluteos", .09, .9, .095, .085, -1, 0],
      ["cuadriceps", .11, .69, .075, .125, 1, 0],
      ["isquiotibiales", .11, .67, .07, .115, -1, 0],
      ["pantorrillas", .135, .33, .055, .105, -1, -.04],
      ["zona_lumbar", 0, 1.05, .05, .085, -1, 0],
      ["rodillas", .112, .51, .06, .055, 0, 0],
      ["cuello", 0, 1.515, .055, .042, 0, 0],
    ]),
  },
};

const TEMAS = {
  claro: {cuerpo: "#e9dfcd", dolor: "#e0401a", trabajada: "#128a5e", volumenBajo: "#dc9273", volumenAlto: "#a12c10", aro: "#b5a993", cielo: 1.7, suelo: "#a89b84", sol: 2.3, solColor: "#fff3e0", contra: 1.2, exposicion: 1, emision: .75, sombra: .22},
  oscuro: {cuerpo: "#d9cdb8", dolor: "#f0603a", trabajada: "#3fb488", volumenBajo: "#a4583c", volumenAlto: "#f0603a", aro: "#5c554a", cielo: 1.2, suelo: "#5c554a", sol: 2.3, solColor: "#ffd9ad", contra: 3, exposicion: 1.05, emision: .4, sombra: .6},
};

const suave = t => t * t * (3 - 2 * t);
const entre01 = t => Math.min(Math.max(t, 0), 1);

// Lleva los brazos del modelo a la cruz, donde se definen las zonas.
function enderezar({pivote, caida, axila}, x, y, z) {
  const linea = axila.x + Math.max(axila.y - y, 0) * axila.pendiente;
  const t = entre01((Math.abs(x) - linea) / .04);
  if (!t) return [x, y, z];
  const angulo = caida * suave(t);
  const dx = Math.abs(x) - pivote.x, dy = y - pivote.y;
  const seno = Math.sin(angulo), coseno = Math.cos(angulo);
  return [Math.sign(x) * (pivote.x + dx * coseno - dy * seno), pivote.y + dx * seno + dy * coseno, z];
}

// Lo inverso, para ubicar sobre el modelo un punto definido en la cruz.
function doblar({pivote, caida}, x, y, z) {
  const t = y < 1.15 ? 0 : entre01((Math.abs(x) - pivote.x + .05) / .13);
  if (!t) return [x, y, z];
  const angulo = caida * suave(t);
  const dx = Math.abs(x) - pivote.x, dy = y - pivote.y;
  const seno = Math.sin(angulo), coseno = Math.cos(angulo);
  return [Math.sign(x) * (pivote.x + dx * coseno + dy * seno), pivote.y - dx * seno + dy * coseno, z];
}

// Un toque cerca de una zona también la elige: las zonas no cubren todo el cuerpo.
function zonaDelPunto({parches}, x, y, z) {
  const lateral = Math.abs(x);
  let elegida = -1, mejor = 1.9;
  for (const parche of parches) {
    const delLado = parche.lado === 0 || (z - parche.corte) * parche.lado >= 0;
    const distancia = Math.hypot((lateral - parche.x) / parche.rx, (y - parche.y) / parche.ry) + (delLado ? 0 : 1);
    if (distancia < mejor) { mejor = distancia; elegida = parche.zona; }
  }
  return elegida;
}

const SOMBREADO = `
  uniform vec4 uParche[${ZONAS_CUERPO.length}];
  uniform vec2 uLado[${ZONAS_CUERPO.length}];
  uniform int uZona[${ZONAS_CUERPO.length}];
  uniform vec3 uRelleno[${ZONAS_CUERPO.length}];
  uniform vec3 uBorde[${ZONAS_CUERPO.length}];
  uniform float uFuerza[${ZONAS_CUERPO.length}];
  uniform float uEmision;
  varying vec3 vReposo;
  // La zona marcada brilla desde su centro y se funde con el cuerpo, sin borde.
  vec4 brilloZona(vec3 punto) {
    vec3 q = vec3(abs(punto.x), punto.y, punto.z);
    vec3 color = vec3(0.0);
    float alfa = 0.0;
    for (int i = 0; i < ${ZONAS_CUERPO.length}; i++) {
      float fuerza = uFuerza[uZona[i]];
      if (fuerza == 0.0) continue;
      float lado = uLado[i].x == 0.0 ? 1.0 : smoothstep(-.018, .018, (q.z - uLado[i].y) * uLado[i].x);
      float d = length((q.xy - uParche[i].xy) / uParche[i].zw);
      float a = (1.0 - smoothstep(.3, 1.12, d)) * lado * fuerza;
      if (a <= alfa) continue;
      alfa = a;
      color = mix(uBorde[uZona[i]], uRelleno[uZona[i]], smoothstep(.25, .7, d));
    }
    return vec4(color, alfa);
  }
`;

// nombreFigura es la elegida por el usuario; sin elección se muestra la masculina (ADR 0020).
// guardarFigura, si llega, agrega el control para elegirla.
export async function crearCuerpo(contenedor, svg, seleccionable, nombreFigura, guardarFigura) {
  let figura = FIGURAS[nombreFigura] ?? FIGURAS.masculina;
  const documento = contenedor.ownerDocument;
  const ventana = documento.defaultView;
  const crear = (nombre, clase, texto) => {
    const nodo = documento.createElement(nombre);
    if (clase) nodo.className = clase;
    if (texto) nodo.textContent = texto;
    return nodo;
  };
  const lienzo = documento.createElement("canvas");
  lienzo.style.cssText = "width:100%;height:var(--alto-cuerpo,400px);display:block;touch-action:pan-y";
  lienzo.setAttribute("aria-label", "Cuerpo 3D muscular. Arrastrá para girar; elegí zonas en la lista.");
  const dibujante = new THREE.WebGLRenderer({canvas: lienzo, antialias: true, alpha: true});
  dibujante.setPixelRatio(Math.min(ventana.devicePixelRatio, 2));
  dibujante.toneMapping = THREE.ACESFilmicToneMapping;
  const escena = new THREE.Scene();
  const cuerpo = new THREE.Group(); escena.add(cuerpo);
  const camara = new THREE.PerspectiveCamera(36, 1, .01, 30);
  camara.position.set(0, 1.05, 3.7); camara.lookAt(0, .8, 0);
  const cielo = new THREE.HemisphereLight(0xffffff, 0x5c554a, 1);
  escena.add(cielo);
  const sol = new THREE.DirectionalLight(0xffffff, 1);
  sol.position.set(1.6, 3.6, 2.6);
  escena.add(sol);
  // Luz de contra: separa la silueta del fondo.
  const contra = new THREE.DirectionalLight(0xffffff, 1);
  contra.position.set(-1.8, 2.4, -3);
  escena.add(contra);
  const compartidos = {
    uParche: {value: []},
    uLado: {value: []},
    uZona: {value: []},
    uRelleno: {value: new Float32Array(ZONAS_CUERPO.length * 3)},
    uBorde: {value: new Float32Array(ZONAS_CUERPO.length * 3)},
    uFuerza: {value: new Float32Array(ZONAS_CUERPO.length)},
    uEmision: {value: 0},
  };
  const material = new THREE.MeshStandardMaterial({roughness: .62, side: THREE.DoubleSide});
  material.onBeforeCompile = sombreador => {
    Object.assign(sombreador.uniforms, compartidos);
    sombreador.vertexShader = sombreador.vertexShader
      .replace("#include <common>", "#include <common>\nattribute vec3 reposo;\nvarying vec3 vReposo;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvReposo = reposo;");
    sombreador.fragmentShader = sombreador.fragmentShader
      .replace("#include <common>", `#include <common>\n${SOMBREADO}`)
      .replace("#include <color_fragment>", "#include <color_fragment>\nvec4 brillo = brilloZona(vReposo);\ndiffuseColor.rgb = mix(diffuseColor.rgb, brillo.rgb, brillo.a);")
      .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\ntotalEmissiveRadiance += brillo.rgb * brillo.a * uEmision;");
  };
  // Sin plataforma: una sombra difusa bajo los pies, que no depende del giro, y un aro fino.
  const materialBase = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: {uOpacidad: {value: 0}},
    vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: "uniform float uOpacidad; varying vec2 vUv; void main() { float d = 1.0 - smoothstep(.05, 1.0, length(vUv - .5) * 2.0); gl_FragColor = vec4(0.0, 0.0, 0.0, uOpacidad * d * d); }",
  });
  const base = new THREE.Mesh(new THREE.CircleGeometry(.62, 64), materialBase);
  base.rotation.x = -Math.PI / 2;
  escena.add(base);
  const materialAro = new THREE.MeshBasicMaterial({transparent: true, opacity: .7});
  const aro = new THREE.Mesh(new THREE.RingGeometry(.47, .478, 96), materialAro);
  aro.rotation.x = -Math.PI / 2;
  aro.position.y = .001;
  escena.add(aro);
  const superficies = [];
  async function cargarModelo() {
    const pedida = figura;
    const {GLTFLoader} = await import('../../vendor/three@0.186.0/loaders/GLTFLoader.js');
    const gltf = await new GLTFLoader().loadAsync(new URL(`../../vendor/cuerpo@2/${pedida.modelo}`, import.meta.url).href);
    // Si eligieron otra mientras cargaba, gana la última.
    if (pedida !== figura) return;
    for (const malla of superficies.splice(0)) { cuerpo.remove(malla); malla.geometry.dispose(); }
    compartidos.uParche.value = figura.parches.flatMap(p => [p.x, p.y, p.rx, p.ry]);
    compartidos.uLado.value = figura.parches.flatMap(p => [p.lado, p.corte]);
    compartidos.uZona.value = figura.parches.map(p => p.zona);
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(objeto => {
      if (!objeto.isMesh) return;
      const geometria = objeto.geometry.clone();
      geometria.applyMatrix4(objeto.matrixWorld);
      const posiciones = geometria.attributes.position.array;
      const reposo = new Float32Array(posiciones.length);
      for (let i = 0; i < posiciones.length; i += 3) {
        reposo.set(enderezar(figura, posiciones[i], posiciones[i + 1], posiciones[i + 2]), i);
      }
      geometria.setAttribute("reposo", new THREE.BufferAttribute(reposo, 3));
      geometria.computeVertexNormals();
      geometria.computeBoundingSphere();
      const malla = new THREE.Mesh(geometria, material);
      cuerpo.add(malla); superficies.push(malla);
    });
  }

  function liberar() {
    for (const malla of superficies) malla.geometry.dispose();
    base.geometry.dispose(); aro.geometry.dispose();
    material.dispose(); materialBase.dispose(); materialAro.dispose();
    dibujante.dispose();
  }
  try { await cargarModelo(); } catch (error) { liberar(); throw error; }
  if (!svg.isConnected || ventana.matchMedia("(prefers-reduced-motion: reduce)").matches) { liberar(); return; }
  const controles = [...svg.querySelectorAll("[data-zona]")];
  const indiceEnFoco = controles.indexOf(documento.activeElement);

  const marco = crear("div", "cuerpo-escena");
  const maqueta = crear("div", "cuerpo-maqueta");
  const cifras = crear("div", "cuerpo-cifras");
  cifras.setAttribute("aria-hidden", "true");
  const rotulos = crear("div", "cuerpo-rotulos");
  rotulos.setAttribute("aria-hidden", "true");
  const giro = crear("div", "cuerpo-giro");
  const frente = crear("button", "", "Frente");
  const espalda = crear("button", "", "Espalda");
  for (const [boton, nombre, destino] of [[frente, "Ver de frente", 0], [espalda, "Ver de espalda", Math.PI]]) {
    boton.type = "button";
    boton.setAttribute("aria-label", nombre);
    boton.addEventListener("click", () => girarHacia(destino));
  }
  giro.append(frente, espalda);
  maqueta.append(lienzo, rotulos, cifras, giro);
  const panel = crear("div", "cuerpo-panel");
  // Con series por zona (el editor de programas) el color es una escala relativa, no un estado.
  const conVolumen = () => controles.some(control => control.dataset.volumen !== undefined);
  const seriesDe = control => Number(control.dataset.series ?? 0);
  panel.append(crear("p", "cuerpo-pista", seleccionable ? "Tocá el cuerpo o elegí una zona. Arrastrá para girar." : "Arrastrá para girar."));
  const lista = crear("div", "cuerpo-zonas");
  lista.setAttribute("aria-label", "Zonas del cuerpo");
  const filas = controles.map((control, indice) => {
    const boton = documento.createElement(seleccionable ? "button" : "p");
    if (seleccionable) {
      boton.type = "button";
      boton.setAttribute("role", "checkbox");
      boton.addEventListener("click", () => control.dispatchEvent(new ventana.MouseEvent("click")));
      // Igual que la silueta: alternar al presionar, sin clic nativo al soltar
      // Espacio si el foco pasó al 3D durante la pulsación.
      boton.addEventListener("keydown", evento => {
        if (evento.key === " " || evento.key === "Enter") {
          evento.preventDefault(); boton.click();
        }
      });
      boton.addEventListener("keyup", evento => {
        if (evento.key === " ") evento.preventDefault();
      });
    }
    boton.dataset.zona = control.dataset.zona;
    const marca = crear("i", "marca-zona");
    const estado = crear("span", "cuerpo-estado");
    boton.append(crear("span", "", ZONAS_CUERPO[indice].nombre), estado, marca);
    lista.append(boton);
    return {boton, marca, estado};
  });
  panel.append(lista);
  if (seleccionable) {
    // El cuerpo manda: la lista muestra lo marcado y el resto se abre a pedido.
    const verTodas = crear("button", "cuerpo-ver-todas");
    verTodas.type = "button";
    const mostrar = abierta => {
      lista.dataset.colapsada = String(!abierta);
      verTodas.textContent = abierta ? "Ocultar zonas sin marcar" : "Ver todas las zonas";
      verTodas.setAttribute("aria-expanded", String(abierta));
    };
    verTodas.addEventListener("click", () => mostrar(lista.dataset.colapsada === "true"));
    mostrar(false);
    panel.append(verTodas);
  }
  if (guardarFigura) {
    const eleccion = crear("div", "cuerpo-figura");
    eleccion.setAttribute("role", "group");
    eleccion.setAttribute("aria-label", "Figura del cuerpo");
    const aviso = crear("p", "cuerpo-pista", "La figura solo cambia cómo se ve este cuerpo y se guarda en tu cuenta.");
    let elegida = FIGURAS[nombreFigura] ? nombreFigura : null;
    const botones = [["masculina", "Masculina"], ["femenina", "Femenina"]].map(([nombre, texto]) => {
      const boton = crear("button", "", texto);
      boton.type = "button";
      boton.setAttribute("aria-pressed", String(nombre === elegida));
      boton.addEventListener("click", async () => {
        if (nombre === elegida) return;
        const anterior = elegida;
        const marcar = valor => {
          elegida = valor;
          figura = FIGURAS[valor] ?? FIGURAS.masculina;
          for (const [otro, otroNombre] of botones) otro.setAttribute("aria-pressed", String(otroNombre === valor));
        };
        marcar(nombre);
        const resultados = await Promise.allSettled([cargarModelo(), guardarFigura(nombre)]);
        // Si eligieron otra mientras tanto, esa elección manda.
        if (!lienzo.isConnected || elegida !== nombre) return;
        const fallo = resultados.some(({status}) => status === "rejected");
        if (fallo) {
          // Vuelve a la figura anterior para que el reintento repita todo.
          marcar(anterior);
          await cargarModelo().catch(() => {});
          if (!lienzo.isConnected) return;
        }
        dibujar();
        aviso.textContent = fallo ? "No se pudo cambiar la figura. Probá de nuevo." : "La figura solo cambia cómo se ve este cuerpo y se guarda en tu cuenta.";
      });
      return [boton, nombre];
    });
    eleccion.append(...botones.map(([boton]) => boton));
    panel.append(eleccion, aviso);
  }
  marco.append(maqueta, panel);

  const oscuro = ventana.matchMedia("(prefers-color-scheme: dark)");
  const color = new THREE.Color();
  const pintar = (arreglo, indice, valor) => color.set(valor).toArray(arreglo, indice * 3);
  const conDolor = control => control.getAttribute("aria-checked") === "true" || control.dataset.dolor === "true";
  const trabajada = control => control.dataset.trabajada === "true";
  // Solo lleva color lo que se marcó o se trabajó. Con ambos estados, el dolor queda en el centro.
  const volumenVisto = new Float32Array(ZONAS_CUERPO.length);
  const colorBajo = new THREE.Color(), colorAlto = new THREE.Color();
  // Cada cambio llega al cuerpo en unos cuadros, para que se note qué zona se movió.
  function avanzarVolumen() {
    let falta = false;
    controles.forEach((control, indice) => {
      const meta = Number(control.dataset.volumen ?? 0);
      const distancia = meta - volumenVisto[indice];
      if (Math.abs(distancia) < .006) { volumenVisto[indice] = meta; return; }
      volumenVisto[indice] += distancia * .24;
      falta = true;
    });
    return falta;
  }
  function pintarVolumen(tema) {
    colorBajo.set(tema.volumenBajo); colorAlto.set(tema.volumenAlto);
    controles.forEach((control, indice) => {
      const visto = volumenVisto[indice];
      color.copy(colorBajo).lerp(colorAlto, visto);
      color.toArray(compartidos.uRelleno.value, indice * 3);
      color.toArray(compartidos.uBorde.value, indice * 3);
      compartidos.uFuerza.value[indice] = visto > .005 ? Math.min(.4 + visto * .58, .98) : 0;
      const {boton, estado} = filas[indice];
      const series = seriesDe(control);
      boton.dataset.estado = series ? "volumen" : "libre";
      boton.style.order = String(-series);
      boton.style.setProperty("--volumen", control.dataset.volumen ?? "0");
      estado.textContent = String(series);
    });
  }
  function pintarZonas(tema) {
    if (conVolumen()) { pintarVolumen(tema); return; }
    controles.forEach((control, indice) => {
      const dolor = conDolor(control), hecha = trabajada(control);
      pintar(compartidos.uRelleno.value, indice, hecha ? tema.trabajada : tema.dolor);
      pintar(compartidos.uBorde.value, indice, dolor ? tema.dolor : tema.trabajada);
      compartidos.uFuerza.value[indice] = dolor || hecha ? .96 : 0;
      const {boton, marca, estado} = filas[indice];
      const clase = hecha && dolor ? "ambas" : dolor ? "dolor" : hecha ? "trabajada" : "";
      marca.className = `marca-zona ${clase}`;
      boton.dataset.estado = clase || "libre";
      if (seleccionable) {
        boton.setAttribute("aria-checked", String(dolor));
        boton.disabled = control.getAttribute("aria-disabled") === "true";
      } else {
        estado.textContent = [hecha && "trabajada", dolor && "con dolor"].filter(Boolean).join(" · ");
      }
    });
  }

  function dibujarCifras() {
    if (conVolumen()) {
      const total = svg.dataset.total ?? "0";
      cifras.replaceChildren(crear("strong", "", total), crear("span", "", total === "1" ? "serie por semana" : "series por semana"));
      return;
    }
    const dolores = controles.filter(conDolor).length;
    const hechas = controles.filter(trabajada).length;
    if (seleccionable) {
      cifras.replaceChildren(crear("strong", "", String(dolores)), crear("span", "", dolores === 1 ? "zona con dolor" : "zonas con dolor"));
    } else {
      cifras.replaceChildren(crear("strong", "", String(hechas)), crear("span", "", hechas === 1 ? "zona trabajada" : "zonas trabajadas"), crear("span", "", `${dolores} con dolor`));
    }
  }

  const punto = new THREE.Vector3();
  function dibujarRotulos(ancho, alto) {
    const nuevos = [];
    const seno = Math.sin(cuerpo.rotation.y), coseno = Math.cos(cuerpo.rotation.y);
    const volumen = conVolumen();
    // Con volumen solo se rotulan las cuatro zonas más trabajadas: el resto está en la lista.
    const destacadas = volumen ? [...controles].filter(seriesDe).sort((a, b) => seriesDe(b) - seriesDe(a)).slice(0, 4) : [];
    controles.forEach((control, indice) => {
      if (volumen ? !destacadas.includes(control) : !conDolor(control) && !trabajada(control)) return;
      const parche = figura.parches.find(p => p.zona === indice);
      // Del lado del cuerpo que mira a la cámara; si ambos se ven, el que queda a la derecha de la pantalla.
      const profundidad = parche.lado === 0 ? .1 : parche.corte + parche.lado * .13;
      const [uno, otro] = [1, -1].map(signo => {
        const [x, y, z] = doblar(figura, signo * (parche.x + parche.rx), parche.y, profundidad);
        return {x: x * coseno + z * seno, y, z: -x * seno + z * coseno};
      });
      const lugar = Math.abs(uno.z - otro.z) < .08 ? (uno.x > otro.x ? uno : otro) : (uno.z > otro.z ? uno : otro);
      if (parche.lado !== 0 && lugar.z < 0) return;
      punto.set(lugar.x, lugar.y, lugar.z).project(camara);
      const rotulo = crear("span", "rotulo-cuerpo", volumen ? `${ZONAS_CUERPO[indice].nombre} ${seriesDe(control)}` : ZONAS_CUERPO[indice].nombre);
      rotulo.style.left = `${(punto.x + 1) / 2 * ancho}px`;
      rotulo.style.top = `${(1 - punto.y) / 2 * alto}px`;
      nuevos.push({elemento: rotulo, izquierda: (punto.x + 1) / 2 * ancho, arriba: (1 - punto.y) / 2 * alto});
    });
    rotulos.replaceChildren(...nuevos.map(n => n.elemento));
    const medidos = nuevos.map(n => ({...n, ancho: n.elemento.offsetWidth, alto: n.elemento.offsetHeight}));
    for (const {elemento, arriba} of separarRotulos(medidos)) elemento.style.top = `${arriba}px`;
  }

  let cuadroVolumen = 0;
  function dibujar() {
    if (conVolumen() && avanzarVolumen() && !cuadroVolumen) {
      cuadroVolumen = ventana.requestAnimationFrame(() => { cuadroVolumen = 0; dibujar(); });
    }
    const tema = oscuro.matches ? TEMAS.oscuro : TEMAS.claro;
    material.color.set(tema.cuerpo);
    materialAro.color.set(tema.aro);
    materialBase.uniforms.uOpacidad.value = tema.sombra;
    compartidos.uEmision.value = tema.emision;
    contra.intensity = tema.contra;
    const deFrente = Math.cos(cuerpo.rotation.y) >= 0;
    frente.setAttribute("aria-pressed", String(deFrente));
    espalda.setAttribute("aria-pressed", String(!deFrente));
    cielo.intensity = tema.cielo;
    cielo.groundColor.set(tema.suelo);
    sol.intensity = tema.sol;
    sol.color.set(tema.solColor);
    dibujante.toneMappingExposure = tema.exposicion;
    pintarZonas(tema);
    dibujarCifras();
    const {width, height} = lienzo.getBoundingClientRect();
    const ancho = Math.max(width, 1), alto = Math.max(height, 1);
    dibujante.setSize(ancho, alto, false);
    camara.aspect = ancho / alto; camara.updateProjectionMatrix();
    dibujante.render(escena, camara);
    dibujarRotulos(ancho, alto);
  }

  let animacion = 0;
  function girarHacia(destino) {
    ventana.cancelAnimationFrame(animacion);
    const inicio = cuerpo.rotation.y;
    // La vuelta más corta, sea cual sea el giro acumulado por arrastre.
    const delta = Math.atan2(Math.sin(destino - inicio), Math.cos(destino - inicio));
    const comienzo = ventana.performance.now();
    const paso = ahora => {
      const t = Math.min(Math.max((ahora - comienzo) / 520, 0), 1);
      cuerpo.rotation.y = inicio + delta * (1 - (1 - t) ** 3);
      dibujar();
      if (t < 1) animacion = ventana.requestAnimationFrame(paso);
    };
    animacion = ventana.requestAnimationFrame(paso);
  }

  let arrastre;
  lienzo.addEventListener("pointerdown", e => {
    ventana.cancelAnimationFrame(animacion);
    arrastre = {x: e.clientX, inicio: e.clientX, y: e.clientY};
    lienzo.setPointerCapture(e.pointerId);
  });
  lienzo.addEventListener("pointermove", e => {
    if (!arrastre) return;
    cuerpo.rotation.y += (e.clientX - arrastre.x) * .012;
    arrastre.x = e.clientX; dibujar();
  });
  lienzo.addEventListener("pointerup", e => {
    if (seleccionable && arrastre && Math.hypot(e.clientX-arrastre.inicio, e.clientY-arrastre.y) < 5) {
      const rect = lienzo.getBoundingClientRect();
      const rayo = new THREE.Raycaster();
      rayo.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1, -(e.clientY-rect.top)/rect.height*2+1), camara);
      const impacto = rayo.intersectObjects(superficies)[0];
      if (impacto) {
        const reposo = impacto.object.geometry.attributes.reposo;
        const {a, b, c} = impacto.face;
        const zona = zonaDelPunto(
          figura,
          (reposo.getX(a) + reposo.getX(b) + reposo.getX(c)) / 3,
          (reposo.getY(a) + reposo.getY(b) + reposo.getY(c)) / 3,
          (reposo.getZ(a) + reposo.getZ(b) + reposo.getZ(c)) / 3,
        );
        if (zona >= 0) filas[zona].boton.click();
      }
    }
    arrastre = null;
  });
  lienzo.addEventListener("pointercancel", () => { arrastre = null; });
  const preferencia = ventana.matchMedia("(prefers-reduced-motion: reduce)");
  const observador = new ventana.MutationObserver(dibujar);
  const ajuste = new ventana.ResizeObserver(dibujar);
  const presencia = new ventana.MutationObserver(() => {
    if (!lienzo.isConnected) restaurar();
  });
  function restaurar() {
    ventana.cancelAnimationFrame(animacion);
    ventana.cancelAnimationFrame(cuadroVolumen);
    observador.disconnect(); ajuste.disconnect(); presencia.disconnect();
    preferencia.removeEventListener("change", restaurar);
    oscuro.removeEventListener("change", dibujar);
    marco.remove(); svg.removeAttribute("hidden"); svg.style.display = "";
    delete contenedor.dataset.cuerpo3d; liberar();
  }
  lienzo.addEventListener("webglcontextlost", e => { e.preventDefault(); restaurar(); }, {once: true});
  preferencia.addEventListener("change", restaurar, {once: true});
  oscuro.addEventListener("change", dibujar);
  svg.before(marco);
  svg.setAttribute("hidden", "");
  svg.style.display = "none";
  observador.observe(svg, {attributes: true, subtree: true});
  ajuste.observe(contenedor); dibujar();
  if (indiceEnFoco >= 0) filas[indiceEnFoco].boton.focus();
  presencia.observe(documento.body, {childList: true, subtree: true});
  contenedor.dataset.cuerpo3d = "listo";
}
