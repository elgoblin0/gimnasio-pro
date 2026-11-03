// Recorrido guiado sobre la app real (ADR 0032): la tarjeta, el avance y lo que cada paso hace en su pantalla.
// Lo carga presentacion.js en cada página mientras haya un recorrido guardado, y la portada al empezarlo.
// Las escrituras pasan por los formularios de cada pantalla, con su Idempotency-Key (ADR 0004).

import { llamarApi } from "./comun/api.js";
import {
  CLAVE_RECORRIDO, DURACION_NARRACION_MS, DURACION_PASO_MS, PASOS, cambioDeSesion, destino, esUltimo, iniciarRecorrido,
  leerRecorrido, pasoActual, progreso, siguiente, textoDeNarracion, textoDelPaso,
} from "./recorrido-pasos.js";

const $ = (selector) => document.querySelector(selector);
const visible = (elemento) => Boolean(elemento?.isConnected && elemento.getClientRects().length && !elemento.closest("[hidden]"));
const sinEfectos = () => document.documentElement.dataset.sinEfectos === "si";

let estado = null;
let hechos = {};
let temporizador = null;
let tarjeta = null;
let ejecucion = 0;
let narrando = false;

function guardar() {
  try { sessionStorage.setItem(CLAVE_RECORRIDO, JSON.stringify(estado)); } catch { /* Sin almacenamiento el recorrido dura esta página. */ }
}

function olvidar() {
  try { sessionStorage.removeItem(CLAVE_RECORRIDO); } catch { /* Nada que borrar. */ }
}

function leer() {
  try { return leerRecorrido(sessionStorage.getItem(CLAVE_RECORRIDO)); } catch { return null; }
}

// Espera a que la pantalla real llegue a un estado; si no llega, el paso sigue con lo que haya.
function esperar(condicion, tope = 15_000) {
  return new Promise((resolver) => {
    const inicio = performance.now();
    const mirar = () => {
      let listo = false;
      try { listo = condicion(); } catch { /* La pantalla todavía no armó lo que se mira. */ }
      if (listo || performance.now() - inicio > tope) resolver(listo);
      else setTimeout(mirar, 100);
    };
    mirar();
  });
}

const pausa = (ms) => new Promise((resolver) => setTimeout(resolver, ms));
const textoDe = (selector) => $(selector)?.textContent.trim() ?? "";

// Lo que la pantalla ya dibujó: leerlo no agrega consultas a la demo.
function ocupacionVisible() {
  const ocupacion = textoDe("[data-ocupacion-cifra]");
  const aforo = textoDe("[data-ocupacion-aforo]").replace(/^de /, "");
  return /^\d+$/.test(ocupacion) && aforo ? { ocupacion, aforo } : {};
}

// Muestra qué va a pasar y da tiempo a leerlo. Si quien mira salió mientras tanto, la acción no sigue.
async function narrar(id, datos) {
  const propia = ejecucion;
  narrando = true;
  mostrar({ texto: textoDeNarracion(id, datos) });
  ubicar();
  // Lo que llega después (la previsión, las fuentes) corre la parte explicada: se vuelve a encuadrar.
  setTimeout(() => { if (propia === ejecucion && narrando) ubicar({ desplazar: true }); }, 700);
  await pausa(DURACION_NARRACION_MS);
  if (propia !== ejecucion) throw new Error("El recorrido ya no está en este paso.");
  narrando = false;
}

// Una repetición más que la vez anterior, si hay con qué comparar: es lo que hace récord y el resumen lo muestra.
function superarLaVezAnterior(formulario, tarjetaEjercicio) {
  const repeticiones = formulario.querySelector("[name=repeticiones]");
  const anteriores = tarjetaEjercicio.textContent.match(/Carga anterior:[^·]*· (\d+) repeticiones/);
  if (repeticiones && anteriores) repeticiones.value = String(Number(anteriores[1]) + 1);
}

async function registrarSerie(formulario) {
  const rir = formulario.querySelector("[name=rir]");
  if (rir && !rir.value) rir.value = "2";
  formulario.requestSubmit();
  await esperar(() => textoDe("[data-estado]") === "Serie guardada." || textoDe("[data-estado]").startsWith("No se"));
  return textoDe("[data-estado]") === "Serie guardada.";
}

// Cada acción espera su pantalla, hace lo que el paso muestra y devuelve lo que encontró para el texto.
const ACCIONES = {
  async entrada() {
    await esperar(() => textoDe("[data-estado]") === "Recepción lista." || textoDe("[data-estado]").endsWith("registrada."));
    const opcion = [...document.querySelectorAll("#socio option")].find((o) => o.textContent.startsWith("Lucía Benítez"));
    if (!opcion) return { resultado: "rechazada" };
    await narrar("entrada", ocupacionVisible());
    const selector = $("#socio");
    selector.value = opcion.value;
    // Elegir el socio abre su tarjeta contextual, como cuando recepción lo busca.
    selector.dispatchEvent(new Event("change"));
    if ([...document.querySelectorAll("[data-visitas] h3")].some((titulo) => titulo.textContent.startsWith("Lucía Benítez"))) {
      return { resultado: "ya-adentro" };
    }
    $("[data-entrada]").requestSubmit();
    await esperar(() => ["Entrada registrada.", "La operación fue rechazada.", "No se confirmó la operación. Podés reintentar o descartar el reintento."].includes(textoDe("[data-estado]")));
    if (textoDe("[data-estado]") !== "Entrada registrada.") return { resultado: "rechazada", motivo: textoDe("[data-error]") };
    return { resultado: "registrada", ...ocupacionVisible() };
  },

  async escena() {
    // La tarjeta contextual de Lucía tapa la escena: se cierra como lo haría recepción.
    if ($("[data-tarjeta-contextual]")?.open) $("[data-cerrar-tarjeta]").click();
    await esperar(() => visible($("[data-escena-ocupacion]")) || visible($("[data-alternativa-escena]")), 4_000);
    return { conEscena: visible($("[data-escena-ocupacion]")) && !visible($("[data-alternativa-escena]")) };
  },

  async chequeo() {
    await esperar(() => textoDe("[data-estado]") === "Propuesta actualizada.");
    // En otra vuelta del mismo día Lucía ya entrenó: el recorrido sigue con una sesión nueva.
    if (visible($("[data-otra-sesion]"))) {
      $("[data-otra-sesion]").click();
      await esperar(() => textoDe("[data-estado]") === "Propuesta actualizada.");
    }
    try { estado.datos.lucia = (await llamarApi("/api/sesion")).usuario?.id ?? estado.datos.lucia; guardar(); } catch { /* La bandeja se abre sin la hoja. */ }
    const formulario = $("[data-formulario-chequeo]");
    // Otra vuelta del mismo día: el chequeo ya está guardado, pero el relato lo vuelve a mostrar.
    if (!new URLSearchParams(location.search).get("sesion")) $("[data-chequeo]").hidden = false;
    if (!visible(formulario)) return {};
    // Durmió mal, y se ve: el formulario queda completo mientras se lee. El chequeo desfavorable recorta la
    // propuesta y activa el freno que verá el entrenador.
    $('input[name="sueno"][value="1"]').checked = true;
    $('input[name="energia"][value="2"]').checked = true;
    await narrar("chequeo");
    formulario.requestSubmit();
    const guardado = await esperar(() => !visible($("[data-chequeo]")) && !["Registrando…", "Cargando tu propuesta…"].includes(textoDe("[data-estado]")));
    return { chequeo: guardado && !textoDe("[data-error]") ? "guardado" : "sin-chequeo" };
  },

  async series() {
    if (!visible($("[data-sesion-actual]"))) {
      await esperar(() => visible($("[data-iniciar]")) && !$("[data-iniciar]").disabled);
      $("[data-iniciar]").click();
      await esperar(() => textoDe("[data-estado]") === "Sesión iniciada." || Boolean(textoDe("[data-error]")));
      if (!visible($("[data-sesion-actual]"))) return { resultado: "rechazada", motivo: textoDe("[data-error]") };
    }
    estado.datos.sesion = new URLSearchParams(location.search).get("sesion") ?? estado.datos.sesion;
    guardar();
    // Una serie de cada uno de los dos primeros ejercicios: el resumen ilumina más de una zona del cuerpo.
    let ejercicio;
    let series = 0;
    const ejercicios = [...document.querySelectorAll("[data-ejercicio]")].slice(0, 2).map((elemento) => elemento.dataset.ejercicio);
    for (const id of ejercicios) {
      // Se ve un ejercicio a la vez: el siguiente se abre como lo haría el socio.
      document.querySelector(`[data-foco-ejercicio="${CSS.escape(id)}"]`)?.click();
      // Cada serie guardada redibuja la lista: la tarjeta y su formulario se buscan de nuevo.
      const formulario = document.querySelector(`[data-serie="${CSS.escape(id)}"]`);
      if (!visible(formulario) || !formulario.checkValidity()) continue;
      const nombre = formulario.querySelector("button[type=submit]").getAttribute("aria-label").replace(/^Registrar serie de /, "");
      superarLaVezAnterior(formulario, formulario.closest("[data-ejercicio]"));
      await pausa(sinEfectos() ? 0 : 900);
      if (!await registrarSerie(formulario)) break;
      ejercicio ??= nombre;
      series += 1;
    }
    return series
      ? { resultado: "registrada", ejercicio, series }
      : { resultado: "rechazada", motivo: textoDe("[data-error]") };
  },

  async freno() {
    if (!new URLSearchParams(location.search).get("socio")) {
      await esperar(() => !textoDe("[data-estado]").startsWith("Cargando"));
      return { resultado: "ya-revisado" };
    }
    await esperar(() => visible($("[data-socio]")) || Boolean(textoDe("[data-socio-error]")));
    if (!visible($("[data-revision]"))) return { resultado: "ya-revisado" };
    await narrar("freno");
    $("[data-formulario-revision]").requestSubmit();
    // El sondeo de la bandeja reescribe su estado: lo que dice si se revisó es la hoja redibujada.
    const revisado = await esperar(() => !visible($("[data-revision]")) && visible($("[data-historial]")) || Boolean(textoDe("[data-error-revision]")));
    return { resultado: revisado && !textoDe("[data-error-revision]") ? "revisado" : "ya-revisado" };
  },

  async resumen() {
    await esperar(() => textoDe("[data-estado]") === "Resumen actualizado." || Boolean(textoDe("[data-error]")));
    if (!visible($("[data-resumen]"))) return {};
    const records = textoDe("[data-records]").startsWith("Sin récords") ? 0 : document.querySelectorAll("[data-records] li").length;
    return { zonas: document.querySelectorAll("[data-zonas-texto] li").length, records };
  },
};

function crearTarjeta() {
  const aparte = document.createElement("aside");
  aparte.className = "recorrido";
  aparte.dataset.recorridoTarjeta = "";
  aparte.setAttribute("aria-label", "Recorrido guiado");
  aparte.innerHTML = `
    <p class="recorrido-paso" data-recorrido-progreso></p>
    <p class="recorrido-texto" data-recorrido-texto></p>
    <p class="solo-lector" data-recorrido-anuncio aria-live="polite" aria-atomic="true"></p>
    <div class="recorrido-tiempo" aria-hidden="true"><span data-recorrido-tiempo></span></div>
    <div class="recorrido-acciones">
      <button type="button" class="boton-tinta" data-recorrido-siguiente>Siguiente</button>
      <button type="button" class="boton-borde" data-recorrido-pausa aria-pressed="false">Pausar</button>
      <button type="button" class="boton-enlace" data-recorrido-salir>Salir del recorrido</button>
    </div>`;
  aparte.querySelector("[data-recorrido-siguiente]").addEventListener("click", avanzar);
  aparte.querySelector("[data-recorrido-pausa]").addEventListener("click", alternarPausa);
  aparte.querySelector("[data-recorrido-salir]").addEventListener("click", () => terminar({ enfocar: true }));
  aparte.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") {
      evento.stopPropagation();
      terminar({ enfocar: true });
    }
  });
  document.body.append(aparte);
  return aparte;
}

function escribiendo(elemento) {
  return elemento?.matches?.("input, select, textarea, [contenteditable='true']");
}

function alTeclado(evento) {
  if (!tarjeta || evento.altKey || evento.ctrlKey || evento.metaKey || evento.shiftKey) return;
  if (evento.key === "ArrowRight" && !escribiendo(document.activeElement) && !tarjeta.querySelector("[data-recorrido-siguiente]").disabled) {
    evento.preventDefault();
    avanzar();
  }
}

// El selector que explica el paso en esta pantalla, y su elemento: vale el primero visible.
function ancla() {
  for (const selector of pasoActual(estado).ancla) {
    const elemento = $(selector);
    if (visible(elemento)) return { selector, elemento };
  }
  return { selector: null, elemento: null };
}

let anclaMostrada = null;

function columnaDesplazable(elemento) {
  for (let padre = elemento.parentElement; padre && padre !== document.body; padre = padre.parentElement) {
    if (/auto|scroll/.test(getComputedStyle(padre).overflowY) && padre.scrollHeight > padre.clientHeight) return padre;
  }
  return null;
}

// Lleva la parte explicada al espacio libre entre la cabecera y la tarjeta: centrada si entra, si no, su comienzo.
function encuadrar(elemento, altoTarjeta) {
  if (getComputedStyle(elemento).position === "fixed") return;
  const margen = 16;
  // Una columna que se desplaza por su cuenta (la hoja de la bandeja en escritorio) la lleva a su propia vista.
  const columna = columnaDesplazable(elemento);
  if (columna) {
    columna.scrollTop += elemento.getBoundingClientRect().top - columna.getBoundingClientRect().top - margen;
    return;
  }
  const cabecera = $("body > .cabecera")?.offsetHeight ?? 0;
  const rect = elemento.getBoundingClientRect();
  const libre = innerHeight - cabecera - altoTarjeta - rect.height;
  const arriba = rect.top + scrollY - cabecera - (libre >= 2 * margen ? libre / 2 : margen);
  scrollTo({ top: Math.max(0, arriba), behavior: sinEfectos() ? "auto" : "smooth" });
}

// La tarjeta va siempre al pie de la vista: nunca se corta ni tapa el comienzo de lo que explica. La página reserva
// su alto solo si hay algo que llevar sobre ella; sin ancla, la pantalla queda como está.
function ubicar({ desplazar = false } = {}) {
  if (!tarjeta) return;
  const { selector, elemento } = ancla();
  for (const marcado of document.querySelectorAll("[data-recorrido-ancla]")) if (marcado !== elemento) delete marcado.dataset.recorridoAncla;
  if (elemento && !("recorridoAncla" in elemento.dataset)) elemento.dataset.recorridoAncla = "";
  // Si la pantalla cambió la parte que se explica, la vista la sigue una vez; un redibujo de la misma, no.
  if (tarjeta.dataset.cargando === "false" && selector !== anclaMostrada) {
    anclaMostrada = selector;
    desplazar = true;
  }
  const altoTarjeta = tarjeta.offsetHeight + 32;
  document.documentElement.style.setProperty("--alto-recorrido", elemento ? `${altoTarjeta}px` : "0px");
  if (desplazar && elemento) encuadrar(elemento, altoTarjeta);
}

let ubicacionPendiente = false;
function ubicarLuego() {
  if (ubicacionPendiente) return;
  ubicacionPendiente = true;
  requestAnimationFrame(() => {
    ubicacionPendiente = false;
    ubicar();
  });
}

function mostrar({ texto, cargando = false }) {
  tarjeta.querySelector("[data-recorrido-progreso]").textContent = `Recorrido · ${progreso(estado).toLowerCase()}`;
  tarjeta.querySelector("[data-recorrido-texto]").textContent = texto;
  tarjeta.dataset.cargando = String(cargando);
  const botonSiguiente = tarjeta.querySelector("[data-recorrido-siguiente]");
  botonSiguiente.disabled = cargando || narrando;
  botonSiguiente.textContent = esUltimo(estado) ? "Terminar recorrido" : "Siguiente";
  const botonPausa = tarjeta.querySelector("[data-recorrido-pausa]");
  botonPausa.hidden = esUltimo(estado);
  botonPausa.textContent = estado.pausado ? "Seguir solo" : "Pausar";
  botonPausa.setAttribute("aria-pressed", String(estado.pausado));
  if (!cargando) tarjeta.querySelector("[data-recorrido-anuncio]").textContent = `${progreso(estado)}. ${texto}`;
}

function programarAvance() {
  clearTimeout(temporizador);
  temporizador = null;
  const barra = tarjeta.querySelector("[data-recorrido-tiempo]");
  barra.getAnimations?.().forEach((animacion) => animacion.cancel());
  const avanzaSolo = !estado.pausado && !esUltimo(estado) && !narrando && tarjeta.dataset.cargando === "false"
    && location.pathname === pasoActual(estado).pagina;
  barra.parentElement.hidden = !avanzaSolo;
  if (!avanzaSolo) return;
  temporizador = setTimeout(avanzar, DURACION_PASO_MS);
  if (!sinEfectos()) barra.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { duration: DURACION_PASO_MS, easing: "linear", fill: "forwards" });
}

function alternarPausa() {
  estado.pausado = !estado.pausado;
  guardar();
  mostrar({ texto: tarjeta.querySelector("[data-recorrido-texto]").textContent, cargando: tarjeta.dataset.cargando === "true" });
  programarAvance();
}

async function ejecutar({ enfocar = false } = {}) {
  const propia = ++ejecucion;
  const paso = pasoActual(estado);
  tarjeta ??= crearTarjeta();
  mostrar({ texto: "Preparando la pantalla…", cargando: true });
  programarAvance();
  ubicar();
  if (enfocar) tarjeta.querySelector("[data-recorrido-pausa]").focus();
  if (location.pathname !== paso.pagina) {
    // Quien siguió un enlace durante el recorrido puede volver al paso o salir.
    mostrar({ texto: "Saliste de la pantalla de este paso. Podés volver al recorrido o salir y seguir por tu cuenta." });
    tarjeta.querySelector("[data-recorrido-siguiente]").textContent = "Volver al recorrido";
    programarAvance();
    return;
  }
  try {
    hechos = (await ACCIONES[paso.id]?.()) ?? {};
  } catch {
    hechos = {};
  }
  if (propia !== ejecucion || !tarjeta) return;
  mostrar({ texto: textoDelPaso(paso.id, hechos) });
  anclaMostrada = null;
  ubicar();
  programarAvance();
  // La pantalla puede terminar de acomodarse después (listas que llegan, fuentes): se vuelve a encuadrar.
  setTimeout(() => { if (propia === ejecucion) ubicar({ desplazar: true }); }, 700);
}

let cambiando = false;
async function avanzar() {
  if (!estado || cambiando) return;
  if (location.pathname !== pasoActual(estado).pagina) {
    location.assign(destino(pasoActual(estado), estado.datos));
    return;
  }
  const nuevo = siguiente(estado);
  if (!nuevo) {
    await volverALaPortada();
    return;
  }
  const anterior = pasoActual(estado);
  const paso = PASOS[nuevo.indice];
  estado = nuevo;
  guardar();
  const sesion = cambioDeSesion(anterior, paso);
  if (!sesion && paso.pagina === anterior.pagina) {
    await ejecutar();
    return;
  }
  cambiando = true;
  clearTimeout(temporizador);
  mostrar({ texto: "Cambiando de pantalla…", cargando: true });
  try {
    if (sesion) await llamarApi(`/api/sesion/demo/${sesion}`, { metodo: "POST" });
    location.assign(destino(paso, estado.datos));
  } catch (error) {
    // Sin el cambio de sesión no se puede seguir: se vuelve al paso anterior para reintentar.
    cambiando = false;
    estado = { ...estado, indice: estado.indice - 1 };
    guardar();
    mostrar({ texto: `${error.message} Podés reintentar con «Siguiente» o salir del recorrido.` });
  }
}

// Terminar invita a explorar: la portada, sin sesión, ofrece entrar como cualquier rol.
async function volverALaPortada() {
  cambiando = true;
  mostrar({ texto: "Volviendo al inicio…", cargando: true });
  try {
    await llamarApi("/api/sesion", { metodo: "DELETE" });
    terminar({ enfocar: false });
    location.assign("/");
  } catch (error) {
    cambiando = false;
    mostrar({ texto: `${error.message} Podés reintentar o salir del recorrido.` });
  }
}

// Al salir se queda en la pantalla real del paso, con la sesión de ese paso.
function terminar({ enfocar }) {
  ejecucion++;
  narrando = false;
  clearTimeout(temporizador);
  olvidar();
  estado = null;
  removeEventListener("keydown", alTeclado);
  removeEventListener("resize", ubicarLuego);
  observador?.disconnect();
  for (const marcado of document.querySelectorAll("[data-recorrido-ancla]")) delete marcado.dataset.recorridoAncla;
  document.documentElement.style.removeProperty("--alto-recorrido");
  tarjeta?.remove();
  tarjeta = null;
  const titulo = enfocar ? document.querySelector("main h1") : null;
  if (titulo) {
    titulo.tabIndex = -1;
    titulo.focus();
  }
}

let observador = null;
function escuchar() {
  addEventListener("keydown", alTeclado);
  addEventListener("resize", ubicarLuego);
  // Las pantallas redibujan su contenido: la marca de la parte explicada la sigue.
  observador = new MutationObserver((cambios) => {
    if (cambios.some((cambio) => !tarjeta?.contains(cambio.target))) ubicarLuego();
  });
  observador.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
}

export function empezarRecorrido() {
  if (estado) terminar({ enfocar: false });
  estado = iniciarRecorrido();
  guardar();
  if (location.pathname !== PASOS[0].pagina) {
    location.assign(PASOS[0].pagina);
    return;
  }
  escuchar();
  ejecutar({ enfocar: true });
}

export function continuarRecorrido() {
  estado ??= leer();
  if (!estado || tarjeta) return;
  escuchar();
  ejecutar();
}

continuarRecorrido();
