// Recorrido guiado sobre la app real (ADR 0032): la tarjeta, el avance y lo que cada paso hace en su pantalla.
// Lo carga presentacion.js en cada página mientras haya un recorrido guardado, y la portada al empezarlo.
// Las escrituras pasan por los formularios de cada pantalla, con su Idempotency-Key (ADR 0004).

import { llamarApi } from "./comun/api.js";
import {
  CLAVE_RECORRIDO, DURACION_PASO_MS, PASOS, cambioDeSesion, destino, esUltimo, iniciarRecorrido, leerRecorrido,
  pasoActual, progreso, siguiente, textoDelPaso,
} from "./recorrido-pasos.js";

const $ = (selector) => document.querySelector(selector);
const visible = (elemento) => Boolean(elemento?.isConnected && elemento.getClientRects().length && !elemento.closest("[hidden]"));
const sinEfectos = () => document.documentElement.dataset.sinEfectos === "si";

let estado = null;
let hechos = {};
let temporizador = null;
let tarjeta = null;
let ejecucion = 0;

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

async function ocupacion() {
  const datos = await llamarApi("/api/ocupacion");
  return { ocupacion: datos.ocupacion_registrada, aforo: datos.aforo_maximo };
}

// Cada acción espera su pantalla, hace lo que el paso muestra y devuelve lo que encontró para el texto.
const ACCIONES = {
  async aforo() {
    await esperar(() => textoDe("[data-estado]") === "Recepción lista.");
    try { return await ocupacion(); } catch { return {}; }
  },

  async entrada() {
    await esperar(() => textoDe("[data-estado]") === "Recepción lista." || textoDe("[data-estado]").endsWith("registrada."));
    const opcion = [...document.querySelectorAll("#socio option")].find((o) => o.textContent.startsWith("Lucía Benítez"));
    if (!opcion) return { resultado: "rechazada" };
    const selector = $("#socio");
    let tarjetaSocio;
    try { tarjetaSocio = await llamarApi(`/api/socios/${opcion.value}/tarjeta`); } catch { tarjetaSocio = null; }
    selector.value = opcion.value;
    selector.dispatchEvent(new Event("change"));
    if (tarjetaSocio?.visita_abierta) return { resultado: "ya-adentro" };
    await pausa(sinEfectos() ? 0 : 900);
    $("[data-entrada]").requestSubmit();
    await esperar(() => ["Entrada registrada.", "La operación fue rechazada.", "No se confirmó la operación. Podés reintentar o descartar el reintento."].includes(textoDe("[data-estado]")));
    if (textoDe("[data-estado]") !== "Entrada registrada.") return { resultado: "rechazada", motivo: textoDe("[data-error]") };
    try { return { resultado: "registrada", ...await ocupacion() }; } catch { return { resultado: "registrada" }; }
  },

  async escena() {
    // La tarjeta contextual de Lucía tapa la escena: se cierra como lo haría recepción.
    if ($("[data-tarjeta-contextual]")?.open) $("[data-cerrar-tarjeta]").click();
    await esperar(() => visible($("[data-escena-ocupacion]")) || visible($("[data-alternativa-escena]")), 4_000);
    return { conEscena: visible($("[data-escena-ocupacion]")) && !visible($("[data-alternativa-escena]")) };
  },

  async propuesta() {
    await esperar(() => textoDe("[data-estado]") === "Propuesta actualizada.");
    try { estado.datos.lucia = (await llamarApi("/api/sesion")).usuario?.id ?? estado.datos.lucia; guardar(); } catch { /* La bandeja se abre sin la hoja. */ }
    const formulario = $("[data-formulario-chequeo]");
    if (!visible(formulario)) return {};
    // Durmió mal: el chequeo desfavorable recorta la propuesta y activa el freno que verá el entrenador.
    $("#chequeo-sueno").value = "1";
    $("#chequeo-energia").value = "5";
    await pausa(sinEfectos() ? 0 : 900);
    formulario.requestSubmit();
    const guardado = await esperar(() => !visible($("[data-chequeo]")) && !["Registrando…", "Cargando tu propuesta…"].includes(textoDe("[data-estado]")));
    return { chequeo: guardado && !textoDe("[data-error]") ? "guardado" : "sin-chequeo" };
  },

  async series() {
    if (!visible($("[data-sesion-actual]"))) {
      await esperar(() => visible($("[data-iniciar]")) && !$("[data-iniciar]").disabled);
      $("[data-iniciar]").click();
      await esperar(() => textoDe("[data-estado]") === "Sesión realizada iniciada." || Boolean(textoDe("[data-error]")));
      if (!visible($("[data-sesion-actual]"))) return { resultado: "rechazada", motivo: textoDe("[data-error]") };
    }
    const formulario = [...document.querySelectorAll("[data-serie]")].find((f) => visible(f) && f.checkValidity());
    if (!formulario) return { resultado: "rechazada" };
    const rir = formulario.querySelector("[name=rir]");
    if (rir && !rir.value) rir.value = "2";
    const ejercicio = formulario.querySelector("button[type=submit]").getAttribute("aria-label").replace(/^Registrar serie de /, "");
    await pausa(sinEfectos() ? 0 : 900);
    formulario.requestSubmit();
    await esperar(() => textoDe("[data-estado]") === "Serie guardada." || textoDe("[data-estado]").startsWith("No se"));
    return textoDe("[data-estado]") === "Serie guardada."
      ? { resultado: "registrada", ejercicio }
      : { resultado: "rechazada", motivo: textoDe("[data-error]") };
  },

  async freno() {
    if (!new URLSearchParams(location.search).get("socio")) {
      await esperar(() => !textoDe("[data-estado]").startsWith("Cargando"));
      return { avisos: 0 };
    }
    await esperar(() => visible($("[data-socio]")) || Boolean(textoDe("[data-socio-error]")));
    return { avisos: visible($("[data-revision]")) ? document.querySelectorAll("[data-avisos-sin-revisar] > li").length : 0 };
  },

  async revision() {
    await esperar(() => visible($("[data-socio]")) || Boolean(textoDe("[data-socio-error]")), 5_000);
    if (!visible($("[data-revision]"))) return { resultado: "ya-revisado" };
    await pausa(sinEfectos() ? 0 : 600);
    $("[data-formulario-revision]").requestSubmit();
    // El sondeo de la bandeja reescribe su estado: lo que dice si se revisó es la hoja redibujada.
    const revisado = await esperar(() => !visible($("[data-revision]")) && visible($("[data-historial]")) || Boolean(textoDe("[data-error-revision]")));
    return { resultado: revisado && !textoDe("[data-error-revision]") ? "revisado" : "ya-revisado" };
  },

  async administracion() {
    await esperar(() => visible($("[data-contenido]")));
    return {};
  },

  async explorar() {
    await esperar(() => visible($("[data-demo]")));
    return {};
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

// En pantallas angostas la tarjeta va al pie; en las anchas, junto a la parte que explica: debajo si entran
// las dos en la vista, si no al costado, y si no hay costado, adentro en su esquina inferior.
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
  const angosta = innerWidth < 720 || !elemento;
  tarjeta.dataset.lugar = angosta ? "pie" : "ancla";
  document.documentElement.style.setProperty("--alto-recorrido", angosta ? `${tarjeta.offsetHeight + 16}px` : "0px");
  const comportamiento = sinEfectos() ? "auto" : "smooth";
  const cabecera = $("body > .cabecera")?.offsetHeight ?? 0;
  const margen = 16;
  if (angosta) {
    tarjeta.style.top = tarjeta.style.left = "";
    if (desplazar && elemento) scrollTo({ top: Math.max(0, elemento.getBoundingClientRect().top + scrollY - cabecera - margen), behavior: comportamiento });
    return;
  }
  const rect = elemento.getBoundingClientRect();
  const caja = { top: rect.top + scrollY, bottom: rect.bottom + scrollY, left: rect.left + scrollX, right: rect.right + scrollX };
  const ancho = tarjeta.offsetWidth;
  const alto = tarjeta.offsetHeight;
  const anchoVista = document.documentElement.clientWidth;
  const altoUtil = innerHeight - cabecera;
  const separacion = 12;
  let arriba;
  let izquierda;
  if (rect.height + separacion + alto <= altoUtil * 0.9) {
    [arriba, izquierda] = [caja.bottom + separacion, caja.left];
  } else if (caja.right + separacion + ancho + margen <= anchoVista) {
    [arriba, izquierda] = [caja.top, caja.right + separacion];
  } else if (caja.left - separacion - ancho >= margen) {
    [arriba, izquierda] = [caja.top, caja.left - separacion - ancho];
  } else {
    [arriba, izquierda] = [caja.bottom - alto - margen, caja.left + margen];
  }
  izquierda = Math.min(Math.max(margen, izquierda), anchoVista - ancho - margen);
  tarjeta.style.top = `${Math.round(arriba)}px`;
  tarjeta.style.left = `${Math.round(izquierda)}px`;
  if (desplazar) {
    const desde = Math.min(caja.top, arriba);
    const hasta = Math.max(caja.bottom, arriba + alto);
    const libre = altoUtil - (hasta - desde);
    const objetivo = libre >= 2 * margen ? desde - cabecera - libre / 2 : arriba - cabecera - margen;
    scrollTo({ top: Math.max(0, objetivo), behavior: comportamiento });
  }
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
  botonSiguiente.disabled = cargando;
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
  const avanzaSolo = !estado.pausado && !esUltimo(estado) && tarjeta.dataset.cargando === "false"
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
    terminar({ enfocar: false });
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
    if (sesion === "ninguna") await llamarApi("/api/sesion", { metodo: "DELETE" });
    else if (sesion) await llamarApi(`/api/sesion/demo/${sesion}`, { metodo: "POST" });
    location.assign(destino(paso, estado.datos));
  } catch (error) {
    // Sin el cambio de sesión no se puede seguir: se vuelve al paso anterior para reintentar.
    cambiando = false;
    estado = { ...estado, indice: estado.indice - 1 };
    guardar();
    mostrar({ texto: `${error.message} Podés reintentar con «Siguiente» o salir del recorrido.` });
  }
}

// Al salir se queda en la pantalla real del paso, con la sesión de ese paso.
function terminar({ enfocar }) {
  ejecucion++;
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
  // Las pantallas redibujan su contenido: la marca de la parte explicada y la tarjeta la siguen.
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
