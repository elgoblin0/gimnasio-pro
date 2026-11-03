import { llamarApi } from "@comun/api.js";
import { formatearCarga, formatearFecha } from "@comun/formatos.js";
import { exigirRol, prepararBarra } from "@comun/personal.js";
import { calcularProgreso, resumirProgreso } from "@comun/progreso.js";

const seccion = document.querySelector("[data-progreso]");
const selector = seccion.querySelector("select");
const estado = seccion.querySelector("[role=status]");
const grafico = seccion.querySelector("svg");
const tabla = seccion.querySelector("tbody");
const cifras = document.querySelector("[data-progreso-cifras]");
let ejercicios = [];
let consulta = 0;
let disponible = false;

function elemento(nombre, atributos, texto) {
  const nodo = document.createElementNS("http://www.w3.org/2000/svg", nombre);
  for (const [clave, valor] of Object.entries(atributos)) nodo.setAttribute(clave, valor);
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
}

function dibujarCifras(puntos) {
  const resumen = resumirProgreso(puntos);
  cifras.hidden = !resumen;
  if (!resumen) return;
  document.querySelector("[data-progreso-ultima]").textContent = formatearCarga(resumen.ultima);
  const cambio = document.querySelector("[data-progreso-cambio]");
  cambio.textContent = resumen.cambio === 0
    ? `Sin cambios en ${resumen.sesiones} ${resumen.sesiones === 1 ? "sesión" : "sesiones"}`
    : `${resumen.cambio > 0 ? "+" : "−"}${formatearCarga(Math.abs(resumen.cambio))} en ${resumen.sesiones} sesiones`;
}

function dibujar() {
  if (!disponible) return;
  const puntos = ejercicios.find((e) => e.id === selector.value)?.puntos ?? [];
  estado.textContent = puntos.length ? "Carga máxima vigente por sesión realizada." : "Todavía no hay cargas registradas para mostrar tu progreso.";
  grafico.toggleAttribute("hidden", !puntos.length);
  grafico.replaceChildren();
  tabla.replaceChildren();
  dibujarCifras(puntos);
  const ancho = Math.max(280, seccion.clientWidth - 48);
  const geometria = calcularProgreso(puntos, { ancho, alto: 320 });
  grafico.setAttribute("viewBox", `0 0 ${ancho} 320`);
  const { escalas: e } = geometria;
  for (const carga of [e.minima, (e.minima + e.maxima) / 2, e.maxima]) {
    const y = e.abajo - (carga - e.minima) / (e.maxima - e.minima) * (e.abajo - e.arriba);
    grafico.append(elemento("line", { x1: e.izquierda, x2: e.derecha, y1: y, y2: y, class: "progreso-guia" }));
    grafico.append(elemento("text", { x: e.izquierda - 8, y: y + 4, "text-anchor": "end" }, `${Number(carga.toFixed(1))}`));
  }
  grafico.append(elemento("path", { d: geometria.trazo, class: "progreso-trazo" }));
  for (const [indice, punto] of geometria.marcas.entries()) {
    const marca = elemento("circle", { cx: punto.x, cy: punto.y, r: 4, class: "progreso-marca" });
    marca.append(elemento("title", {}, `${formatearFecha(punto.fecha_local)}: ${formatearCarga(punto.carga)}, ${punto.repeticiones} repeticiones`));
    grafico.append(marca);
    if (indice === 0 || indice === puntos.length - 1) grafico.append(elemento("text", { x: punto.x, y: 310, "text-anchor": indice === 0 ? "start" : "end" }, formatearFecha(punto.fecha_local)));
    const fila = document.createElement("tr");
    for (const texto of [formatearFecha(punto.fecha_local), formatearCarga(punto.carga), punto.repeticiones ?? "Sin repeticiones"]) {
      const celda = document.createElement("td"); celda.textContent = texto; fila.append(celda);
    }
    tabla.append(fila);
  }
}

async function actualizar() {
  const actual = ++consulta;
  disponible = false;
  grafico.setAttribute("hidden", "");
  cifras.hidden = true;
  tabla.replaceChildren();
  selector.disabled = true;
  estado.textContent = "Cargando progreso…";
  try {
    const datos = await llamarApi("/api/entrenamiento/progreso");
    if (actual !== consulta) return;
    const elegido = selector.value;
    ejercicios = datos.ejercicios;
    selector.replaceChildren(...ejercicios.map((e) => new Option(e.nombre, e.id)));
    if (ejercicios.some((e) => e.id === elegido)) selector.value = elegido;
    selector.disabled = !ejercicios.length;
    disponible = true;
    dibujar();
  } catch (error) {
    if (actual !== consulta) return;
    grafico.setAttribute("hidden", ""); tabla.replaceChildren(); selector.disabled = true;
    estado.textContent = `No se pudo cargar el progreso. ${error.message}`;
  }
}

selector.addEventListener("change", dibujar);
new ResizeObserver(dibujar).observe(seccion);
document.querySelector("[data-actualizar]").addEventListener("click", actualizar);
exigirRol(["socio"]).then((usuario) => { if (usuario) { prepararBarra(usuario); actualizar(); } }).catch(() => {});
