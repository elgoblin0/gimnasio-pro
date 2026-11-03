import * as THREE from "three";
import { ZONAS_CUERPO } from "./zonas.js";
import { esDibujoPorSoftware, graficaDisponible, modoSinEfectos } from "./efectos.js";
import { separarRotulos } from "./volumen-zonas.js";

// Mapa de músculos (scripts/exportar_cuerpo.py): frente y espalda lado a lado, espejados en x. Por texel, R guarda la
// zona (4 bits altos, 15 sin zona) y la zona más cercana (4 bajos), G la distancia al borde y B la coordenada de fibra.
const MAPA = {ancho: .48, alto: 1.84, ladoPx: 256, altoPx: 1024};
const ZONAS_MAPA = 16;

// centros: dónde va el rótulo de cada zona, de frente y de espalda (x, y, z sobre el cuerpo).
const FIGURAS = {
  masculina: {
    modelo: "masculina", centros: {
      cuello: [[.086, 1.511, .052], [.038, 1.543, -.048]], pecho: [[.109, 1.352, .147]],
      dorsales: [[.169, 1.237, .093], [.111, 1.171, -.091]], abdomen: [[.125, 1.043, .111]],
      hombros: [[.23, 1.379, .076], [.227, 1.384, -.094]], biceps: [[.265, 1.24, .056]],
      triceps: [[.315, 1.236, .045], [.252, 1.242, -.081]], cuadriceps: [[.134, .699, .122]],
      rodillas: [[.136, .472, .062], [.147, .455, -.101]], pantorrillas: [[.206, .31, .004], [.139, .329, -.121]],
      espalda_alta: [[.085, 1.392, -.122]], zona_lumbar: [[.031, 1.069, -.076]],
      gluteos: [[.105, .879, -.117]], isquiotibiales: [[.099, .633, -.077]],
    },
  },
  femenina: {
    modelo: "femenina", centros: {
      cuello: [[.083, 1.509, .05], [.035, 1.543, -.04]], pecho: [[.092, 1.354, .16]],
      dorsales: [[.132, 1.249, .159], [.092, 1.171, -.045]], abdomen: [[.114, 1.044, .127]],
      hombros: [[.203, 1.379, .048], [.2, 1.385, -.07]], biceps: [[.222, 1.216, .013]],
      triceps: [[.259, 1.213, .012], [.21, 1.217, -.072]], cuadriceps: [[.134, .699, .104]],
      rodillas: [[.116, .47, .06], [.126, .455, -.083]], pantorrillas: [[.174, .306, .012], [.162, .327, -.1]],
      espalda_alta: [[.078, 1.391, -.089]], zona_lumbar: [[.028, 1.063, -.07]],
      gluteos: [[.111, .883, -.128]], isquiotibiales: [[.097, .63, -.069]],
    },
  },
};

const TEMAS = {
  claro: {cuerpo: "#e9dfcd", dolor: "#e0401a", trabajada: "#128a5e", volumenBajo: "#dc9273", volumenAlto: "#a12c10", aro: "#b5a993", cielo: 1.7, suelo: "#a89b84", sol: 2.3, solColor: "#fff3e0", contra: 1.2, exposicion: 1, emision: .55, sombra: .22, relieve: .42, surco: .3},
  oscuro: {cuerpo: "#d9cdb8", dolor: "#f0603a", trabajada: "#3fb488", volumenBajo: "#a4583c", volumenAlto: "#f0603a", aro: "#5c554a", cielo: 1.2, suelo: "#5c554a", sol: 2.3, solColor: "#ffd9ad", contra: 3, exposicion: 1.05, emision: .4, sombra: .6, relieve: .42, surco: .4},
};

const suave = t => t * t * (3 - 2 * t);
const DURACION_ENCENDIDO = 460;

// Un toque cerca de una zona también la elige: el mapa guarda la más cercana a cada texel.
function zonaDelPunto(datos, x, y, deFrente) {
  if (!datos) return -1;
  const columna = Math.min(Math.floor(Math.abs(x) / MAPA.ancho * MAPA.ladoPx), MAPA.ladoPx - 1) + (deFrente ? 0 : MAPA.ladoPx);
  const fila = Math.min(Math.max(Math.floor((1 - y / MAPA.alto) * MAPA.altoPx), 0), MAPA.altoPx - 1);
  return (datos[(fila * MAPA.ladoPx * 2 + columna) * 4] & 15) - 1;
}

const SOMBREADO = `
  uniform sampler2D uMapa;
  uniform vec3 uRelleno[${ZONAS_MAPA}];
  uniform vec3 uBorde[${ZONAS_MAPA}];
  uniform float uFuerza[${ZONAS_MAPA}];
  uniform float uEncendido[${ZONAS_MAPA}];
  uniform float uEmision;
  uniform float uRelieve;
  uniform float uSurco;
  varying vec3 vPosicion;
  varying vec3 vNormalObjeto;
  // Promedio de 4 texeles a mano: interpolar el código de zona daría otra zona.
  void leerLado(float lado, out float distancia, out float fibra, out float cubre, out float marca, out float encendido, out vec3 color) {
    vec2 lugar = vec2((min(abs(vPosicion.x) / ${MAPA.ancho}, .998) + lado) * ${MAPA.ladoPx}.0, (1.0 - clamp(vPosicion.y / ${MAPA.alto}, 0.0, .998)) * ${MAPA.altoPx}.0) - .5;
    ivec2 base = ivec2(floor(lugar));
    vec2 f = fract(lugar);
    distancia = 0.0; fibra = 0.0; cubre = 0.0; marca = 0.0; encendido = 0.0; color = vec3(0.0);
    for (int j = 0; j < 2; j++) for (int i = 0; i < 2; i++) {
      vec4 texel = texelFetch(uMapa, clamp(base + ivec2(i, j), ivec2(0), ivec2(${MAPA.ladoPx * 2 - 1}, ${MAPA.altoPx - 1})), 0);
      float peso = (i == 0 ? 1.0 - f.x : f.x) * (j == 0 ? 1.0 - f.y : f.y);
      int zona = int(texel.r * 255.0 + .5) >> 4;
      if (zona == 0) continue;
      float fuerza = uFuerza[zona];
      distancia += peso * texel.g;
      fibra += peso * texel.b;
      cubre += peso;
      marca += peso * fuerza;
      encendido += peso * fuerza * uEncendido[zona];
      color += peso * fuerza * mix(uRelleno[zona], uBorde[zona], smoothstep(.45, .85, texel.g));
    }
  }
  vec3 normalConRelieve(vec3 punto, vec3 normalBase, vec2 pendiente, float cara) {
    vec3 sigmaX = normalize(dFdx(punto));
    vec3 sigmaY = normalize(dFdy(punto));
    vec3 r1 = cross(sigmaY, normalBase);
    vec3 r2 = cross(normalBase, sigmaX);
    float det = dot(sigmaX, r1) * cara;
    return normalize(abs(det) * normalBase - sign(det) * (pendiente.x * r1 + pendiente.y * r2));
  }
`;

// Frente y espalda se funden en el costado, donde cae el borde natural de cada músculo.
const LEER_MAPA = `
  float pesoFrente = smoothstep(-.2, .2, normalize(vNormalObjeto).z);
  float mDistancia, mFibra, mCubre, mMarca, mEncendido; vec3 mColor;
  float oDistancia = 0.0, oFibra = 0.0, oCubre = 0.0, oMarca = 0.0, oEncendido = 0.0; vec3 oColor = vec3(0.0);
  leerLado(0.0, mDistancia, mFibra, mCubre, mMarca, mEncendido, mColor);
  if (pesoFrente < 1.0) {
    leerLado(1.0, oDistancia, oFibra, oCubre, oMarca, oEncendido, oColor);
    mDistancia = mix(oDistancia, mDistancia, pesoFrente); mFibra = mix(oFibra, mFibra, pesoFrente);
    mCubre = mix(oCubre, mCubre, pesoFrente); mMarca = mix(oMarca, mMarca, pesoFrente);
    mEncendido = mix(oEncendido, mEncendido, pesoFrente); mColor = mix(oColor, mColor, pesoFrente);
  }
  // El promedio se corrige por la parte cubierta: sin esto, el borde contra la piel dibujaría un surco.
  mDistancia = mCubre > .001 ? mDistancia / mCubre : 1.0;
  float altura = smoothstep(0.0, .34, mDistancia);
  float faseFibra = mFibra * 170.0;
  float fibras = sin(faseFibra) * (1.0 - smoothstep(.5, 1.4, fwidth(faseFibra)));
  // Se enciende del centro del músculo hacia el borde.
  float encendidoVisto = mMarca > .001 ? mEncendido / mMarca : 0.0;
  float frenteEncendido = 1.0 - encendidoVisto * 1.35;
  float alfa = mMarca * smoothstep(frenteEncendido, frenteEncendido + .25, mDistancia);
  vec3 tono = mMarca > .001 ? mColor / mMarca : vec3(0.0);
  float surco = 1.0 - smoothstep(0.0, .22, mDistancia);
  diffuseColor.rgb *= 1.0 - mCubre * (uSurco * surco - .03 * fibras);
  diffuseColor.rgb = mix(diffuseColor.rgb, tono * (1.0 + .16 * fibras) * (1.0 - .35 * surco), alfa);
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
    uMapa: {value: null},
    uRelleno: {value: new Float32Array(ZONAS_MAPA * 3)},
    uBorde: {value: new Float32Array(ZONAS_MAPA * 3)},
    uFuerza: {value: new Float32Array(ZONAS_MAPA)},
    uEncendido: {value: new Float32Array(ZONAS_MAPA)},
    uEmision: {value: 0},
    uRelieve: {value: 0},
    uSurco: {value: 0},
  };
  const material = new THREE.MeshStandardMaterial({roughness: .58, side: THREE.DoubleSide});
  material.onBeforeCompile = sombreador => {
    Object.assign(sombreador.uniforms, compartidos);
    sombreador.vertexShader = sombreador.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vPosicion;\nvarying vec3 vNormalObjeto;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvPosicion = position;\nvNormalObjeto = normal;");
    sombreador.fragmentShader = sombreador.fragmentShader
      .replace("#include <common>", `#include <common>\n${SOMBREADO}`)
      .replace("#include <color_fragment>", `#include <color_fragment>\n${LEER_MAPA}`)
      .replace("#include <normal_fragment_maps>", "#include <normal_fragment_maps>\nnormal = normalConRelieve(-vViewPosition, normal, vec2(dFdx(altura), dFdy(altura)) * uRelieve * mCubre, faceDirection);")
      .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\ntotalEmissiveRadiance += tono * alfa * uEmision * (1.0 + .3 * fibras + surco * .5 + (1.0 - encendidoVisto) * 2.0);");
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
  let datosMapa = null;
  function leerDatosMapa(imagen) {
    const contexto = imagen && documento.createElement("canvas").getContext("2d", {willReadFrequently: true});
    if (!contexto) return null;
    contexto.canvas.width = imagen.width; contexto.canvas.height = imagen.height;
    contexto.drawImage(imagen, 0, 0);
    return contexto.getImageData(0, 0, imagen.width, imagen.height).data;
  }
  async function cargarModelo() {
    const pedida = figura;
    const {GLTFLoader} = await import('../../vendor/three@0.186.0/loaders/GLTFLoader.js');
    const recurso = extension => new URL(`../../vendor/cuerpo@3/${pedida.modelo}.${extension}`, import.meta.url).href;
    const [gltf, mapa] = await Promise.all([new GLTFLoader().loadAsync(recurso("glb")), new THREE.TextureLoader().loadAsync(recurso("png"))]);
    // Si eligieron otra mientras cargaba, gana la última.
    if (pedida !== figura) { mapa.dispose(); return; }
    for (const malla of superficies.splice(0)) { cuerpo.remove(malla); malla.geometry.dispose(); }
    // Son datos, no color: sin filtro, sin corrección y con la fila 0 arriba.
    mapa.flipY = false;
    mapa.generateMipmaps = false;
    mapa.colorSpace = THREE.NoColorSpace;
    mapa.magFilter = mapa.minFilter = THREE.NearestFilter;
    mapa.needsUpdate = true;
    compartidos.uMapa.value?.dispose();
    compartidos.uMapa.value = mapa;
    datosMapa = leerDatosMapa(mapa.image);
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(objeto => {
      if (!objeto.isMesh) return;
      const geometria = objeto.geometry.clone();
      geometria.applyMatrix4(objeto.matrixWorld);
      geometria.computeVertexNormals();
      geometria.computeBoundingSphere();
      const malla = new THREE.Mesh(geometria, material);
      cuerpo.add(malla); superficies.push(malla);
    });
  }

  function liberar() {
    for (const malla of superficies) malla.geometry.dispose();
    base.geometry.dispose(); aro.geometry.dispose();
    compartidos.uMapa.value?.dispose();
    material.dispose(); materialBase.dispose(); materialAro.dispose();
    dibujante.dispose();
  }
  try { await cargarModelo(); } catch (error) { liberar(); throw error; }
  if (!svg.isConnected || modoSinEfectos(documento).activo) { liberar(); return; }
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
  lista.setAttribute("role", "group");
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
  // El código de zona del mapa empieza en 1.
  const pintar = (arreglo, indice, valor) => color.set(valor).toArray(arreglo, (indice + 1) * 3);
  const conDolor = control => control.getAttribute("aria-checked") === "true" || control.dataset.dolor === "true";
  const trabajada = control => control.dataset.trabajada === "true";
  // Solo lleva color lo que se marcó o se trabajó. Con ambos estados, el dolor queda en el centro.
  const encendida = new Float32Array(ZONAS_CUERPO.length);
  const espera = new Float32Array(ZONAS_CUERPO.length);
  // Sin GPU cada cuadro ocupa todos los núcleos: la zona aparece encendida de una vez.
  const sinAnimar = esDibujoPorSoftware(graficaDisponible(documento).renderizador);
  let ultimoAvance = 0;
  // Al abrir, los músculos ya marcados se encienden uno tras otro.
  function escalonarEncendido() {
    controles.filter(control => conDolor(control) || trabajada(control)).forEach((control, orden) => {
      espera[controles.indexOf(control)] = 180 + orden * 110;
    });
  }
  function avanzarEncendido() {
    const ahora = ventana.performance.now();
    const paso = Math.min(ahora - ultimoAvance, 50);
    ultimoAvance = ahora;
    let falta = false;
    controles.forEach((control, indice) => {
      const meta = conDolor(control) || trabajada(control) ? 1 : 0;
      if (sinAnimar) { encendida[indice] = meta; return; }
      if (meta && espera[indice] > 0) { espera[indice] -= paso; falta = true; return; }
      if (encendida[indice] === meta) return;
      const delta = paso / DURACION_ENCENDIDO;
      encendida[indice] = meta > encendida[indice] ? Math.min(encendida[indice] + delta, 1) : Math.max(encendida[indice] - delta * 2, 0);
      falta = true;
    });
    return falta;
  }
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
      color.toArray(compartidos.uRelleno.value, (indice + 1) * 3);
      color.toArray(compartidos.uBorde.value, (indice + 1) * 3);
      compartidos.uFuerza.value[indice + 1] = visto > .005 ? Math.min(.4 + visto * .58, .98) : 0;
      compartidos.uEncendido.value[indice + 1] = 1;
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
      compartidos.uFuerza.value[indice + 1] = encendida[indice] > 0 ? .96 : 0;
      compartidos.uEncendido.value[indice + 1] = suave(encendida[indice]);
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
      // Del lado del cuerpo que mira a la cámara; si ambos se ven, el que queda a la derecha de la pantalla.
      const lugar = figura.centros[ZONAS_CUERPO[indice].id]
        .flatMap(([x, y, z]) => [1, -1].map(signo => ({x: signo * x * coseno + z * seno, y, z: -signo * x * seno + z * coseno})))
        .reduce((mejor, otro) => (Math.abs(otro.z - mejor.z) < .08 ? otro.x > mejor.x : otro.z > mejor.z) ? otro : mejor);
      if (lugar.z < -.02) return;
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
    if ((conVolumen() ? avanzarVolumen() : avanzarEncendido()) && !cuadroVolumen) {
      cuadroVolumen = ventana.requestAnimationFrame(() => { cuadroVolumen = 0; dibujar(); });
    }
    const tema = oscuro.matches ? TEMAS.oscuro : TEMAS.claro;
    material.color.set(tema.cuerpo);
    materialAro.color.set(tema.aro);
    materialBase.uniforms.uOpacidad.value = tema.sombra;
    compartidos.uEmision.value = tema.emision;
    compartidos.uRelieve.value = tema.relieve;
    compartidos.uSurco.value = tema.surco;
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
        const {x, y} = cuerpo.worldToLocal(impacto.point);
        const zona = zonaDelPunto(datosMapa, x, y, impacto.face.normal.z >= 0);
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
    preferencia.removeEventListener("change", alCambiarPreferencia);
    oscuro.removeEventListener("change", dibujar);
    marco.remove(); svg.removeAttribute("hidden"); svg.style.display = "";
    delete contenedor.dataset.cuerpo3d; liberar();
  }
  lienzo.addEventListener("webglcontextlost", e => { e.preventDefault(); restaurar(); }, {once: true});
  // Si el sistema pasa a pedir movimiento reducido, se vuelve a la silueta salvo que se haya elegido a mano.
  function alCambiarPreferencia() { if (modoSinEfectos(documento).activo) restaurar(); }
  preferencia.addEventListener("change", alCambiarPreferencia);
  oscuro.addEventListener("change", dibujar);
  svg.before(marco);
  svg.setAttribute("hidden", "");
  svg.style.display = "none";
  observador.observe(svg, {attributes: true, subtree: true});
  ultimoAvance = ventana.performance.now();
  escalonarEncendido();
  ajuste.observe(contenedor); dibujar();
  if (indiceEnFoco >= 0) filas[indiceEnFoco].boton.focus();
  presencia.observe(documento.body, {childList: true, subtree: true});
  contenedor.dataset.cuerpo3d = "listo";
}
