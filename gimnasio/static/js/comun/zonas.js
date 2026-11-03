import { llamarApi } from "./api.js";
import { graficaDisponible, modoSinEfectos } from "./efectos.js";
import { FIGURA, RELIEVE, TRAZOS } from "./silueta-cuerpo.js";

// Las mismas zonas del cuerpo que el motor. Los trazos salen de los músculos del 3D (scripts/silueta_cuerpo.py).
export const ZONAS_CUERPO = Object.freeze([
  ["pecho", "Pecho"],
  ["espalda_alta", "Espalda alta"],
  ["dorsales", "Dorsales"],
  ["hombros", "Hombros"],
  ["biceps", "Bíceps"],
  ["triceps", "Tríceps"],
  ["abdomen", "Abdomen"],
  ["gluteos", "Glúteos"],
  ["cuadriceps", "Cuádriceps"],
  ["isquiotibiales", "Isquiotibiales"],
  ["pantorrillas", "Pantorrillas"],
  ["zona_lumbar", "Zona lumbar"],
  ["rodillas", "Rodillas"],
  ["cuello", "Cuello"],
].map(([id, nombre]) => Object.freeze({ id, nombre, trazo: TRAZOS[id] })));

export function crearSelectorZonas(contenedor) {
  const documento = contenedor.ownerDocument;
  const seleccionadas = new Set();
  const svg = documento.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 530 400");
  svg.setAttribute("class", "silueta-zonas");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", "Zonas del cuerpo con dolor");
  const elemento = (nombre, atributos) => {
    const nodo = documento.createElementNS(svg.namespaceURI, nombre);
    for (const [clave, valor] of Object.entries(atributos)) nodo.setAttribute(clave, valor);
    return nodo;
  };
  svg.append(
    elemento("path", { d: FIGURA, class: "silueta-base", "aria-hidden": "true" }),
    elemento("path", { d: RELIEVE, class: "silueta-relieve", "aria-hidden": "true" }),
  );
  const controles = ZONAS_CUERPO.map((zona, indice) => {
    const control = elemento("g", { role: "checkbox", tabindex: "0", "aria-label": zona.nombre, "aria-checked": "false", "data-zona": zona.id });
    const region = elemento("path", { d: zona.trazo, class: "silueta-region" });
    const nombre = elemento("text", { x: 392, y: 30 + indice * 26 });
    nombre.textContent = zona.nombre;
    control.append(region, nombre);
    const cambiar = () => {
      if (control.getAttribute("aria-disabled") === "true") return;
      if (seleccionadas.has(zona.id)) seleccionadas.delete(zona.id);
      else seleccionadas.add(zona.id);
      control.setAttribute("aria-checked", String(seleccionadas.has(zona.id)));
    };
    control.addEventListener("click", cambiar);
    control.addEventListener("keydown", (evento) => {
      if (evento.key === " " || evento.key === "Enter") { evento.preventDefault(); cambiar(); }
    });
    svg.append(control);
    return control;
  });
  contenedor.append(svg);
  mejorarCuerpo(contenedor, svg, true);
  return {
    zonas: () => ZONAS_CUERPO.filter((z) => seleccionadas.has(z.id)).map((z) => z.id),
    deshabilitar(valor) {
      for (const control of controles) {
        control.setAttribute("aria-disabled", String(valor));
        control.setAttribute("tabindex", valor ? "-1" : "0");
      }
    },
  };
}

export function crearResumenZonas(contenedor, trabajadas, dolores) {
  crearSelectorZonas(contenedor);
  const original = contenedor.querySelector("svg");
  const svg = original.cloneNode(true);
  original.replaceWith(svg);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Zonas trabajadas y con dolor de la sesión");
  for (const control of svg.querySelectorAll("[data-zona]")) {
    const trabajada = trabajadas.includes(control.dataset.zona);
    const dolor = dolores.includes(control.dataset.zona);
    control.removeAttribute("role");
    control.removeAttribute("tabindex");
    control.removeAttribute("aria-checked");
    control.removeAttribute("aria-label");
    control.dataset.trabajada = String(trabajada);
    control.dataset.dolor = String(dolor);
    const nombre = control.querySelector("text");
    nombre.textContent += `${trabajada ? " · trabajada" : ""}${dolor ? " · con dolor" : ""}`;
  }
  svg.setAttribute("viewBox", "0 0 700 400");
  mejorarCuerpo(contenedor, svg, false);
}

// Series semanales por zona, para quien arma un programa. La figura es la del socio, no la de la sesión,
// y no se elige desde acá. En el modo sin efectos queda la silueta con las series escritas.
export function crearVolumenZonas(contenedor, figura) {
  crearSelectorZonas(contenedor);
  const original = contenedor.querySelector("svg");
  const svg = original.cloneNode(true);
  original.replaceWith(svg);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Series semanales por zona del cuerpo");
  svg.setAttribute("viewBox", "0 0 640 400");
  svg.classList.add("silueta-volumen");
  const controles = [...svg.querySelectorAll("[data-zona]")];
  for (const control of controles) {
    control.removeAttribute("role");
    control.removeAttribute("tabindex");
    control.removeAttribute("aria-checked");
    control.removeAttribute("aria-label");
  }
  mejorarCuerpo(contenedor, svg, false, { figura: figura ?? null });
  return {
    actualizar(volumen, total) {
      const maximo = Math.max(0, ...volumen.values());
      svg.dataset.total = String(total);
      for (const control of controles) {
        const series = volumen.get(control.dataset.zona) ?? 0;
        const relativa = maximo ? series / maximo : 0;
        const zona = ZONAS_CUERPO.find((z) => z.id === control.dataset.zona);
        control.querySelector("text").textContent = `${zona.nombre} · ${series} ${series === 1 ? "serie" : "series"}`;
        control.style.setProperty("--volumen", String(relativa));
        control.dataset.series = String(series);
        control.dataset.volumen = String(relativa);
      }
    },
  };
}

function mejorarCuerpo(contenedor, svg, seleccionable, opciones = {}) {
  // En el modo sin efectos la silueta es el cuerpo. Elegido a mano sin WebGL2, también.
  const documento = contenedor.ownerDocument;
  if (modoSinEfectos(documento).activo || !graficaDisponible(documento).webgl2) return;
  // Después del primer pintado: la silueta se ve enseguida y Three.js no lo demora.
  const ventana = documento.defaultView;
  if (ventana?.requestAnimationFrame) ventana.requestAnimationFrame(() => ventana.setTimeout(() => cargarCuerpo(contenedor, svg, seleccionable, opciones)));
  else cargarCuerpo(contenedor, svg, seleccionable, opciones);
}

function cargarCuerpo(contenedor, svg, seleccionable, opciones) {
  if (!svg.isConnected) return;
  import("./cuerpo-3d.js").then(async ({ crearCuerpo }) => {
    if ("figura" in opciones) {
      if (svg.isConnected) return crearCuerpo(contenedor, svg, seleccionable, opciones.figura);
      return;
    }
    const usuario = await usuarioDeLaSesion();
    if (svg.isConnected) return crearCuerpo(contenedor, svg, seleccionable, usuario?.figura_cuerpo, usuario ? guardarFigura : undefined);
  }).catch(() => {}); // La silueta conserva su función si falla la carga.
}

// Una página puede abrir varios cuerpos: comparten la sesión y la figura elegida en cualquiera de ellos.
let sesion;
const usuarioDeLaSesion = () => sesion ??= llamarApi("/api/sesion").then((datos) => datos.usuario).catch(() => null);

async function guardarFigura(figura) {
  const { usuario } = await llamarApi("/api/sesion/figura-cuerpo", { metodo: "PUT", cuerpo: { figura_cuerpo: figura } });
  sesion = Promise.resolve(usuario);
}
