import { llamarApi } from "@comun/api.js";
import { formatearCarga, formatearFecha } from "@comun/formatos.js";
import { cerrarSesion, crearControlDeOperacion } from "@comun/operaciones.js";
import { prepararMedidas } from "@comun/series.js";
import { registrarPwa } from "@comun/pwa.js";

import { crearDescanso } from "@comun/descanso.js";
import { crearReloj } from "@comun/reloj.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
const reloj = crearReloj();
let descanso = null;
function dibujarDescanso() {
  if (!descanso) return;
  const estado = descanso.consultar(reloj.ahora());
  $("[data-descanso]").hidden = false;
  $("[data-restantes]").textContent = `${estado.restantes} s`;
  const anuncio = estado.terminado ? "Descanso terminado." : "";
  if ($("[data-descanso-anuncio]").textContent !== anuncio) $("[data-descanso-anuncio]").textContent = anuncio;
}
setInterval(dibujarDescanso, 250);
let autorizada = false;
let cargando = false;
let propuestaActual = null;
let sesionActual = null;
let sesionId = new URL(location.href).searchParams.get("sesion");
const control = crearControlDeOperacion();
const numero = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });

function actualizarBotones() {
  for (const elemento of document.querySelectorAll("[data-iniciar], [data-serie] input, [data-serie] button")) {
    elemento.disabled = Boolean(control.actual) || cargando;
  }
  $("[data-actualizar]").disabled = cargando || control.enCurso;
  $("[data-reintento]").hidden = !control.actual || control.enCurso;
  $("[data-reintentar]").disabled = control.enCurso || cargando;
  $("[data-descartar]").disabled = control.enCurso;
}

function agregarFormulario(tarjeta, ejercicio) {
  const formulario = document.createElement("form");
  formulario.dataset.serie = ejercicio.id;
  formulario.noValidate = true;
  const etiquetas = { repeticiones: "Repeticiones", carga: "Carga en kg", duracion: "Duración en segundos", distancia: "Distancia en metros" };
  for (const medida of ejercicio.medidas_aplicables) {
    const etiqueta = document.createElement("label");
    etiqueta.textContent = `${etiquetas[medida]} de ${ejercicio.nombre}`;
    const campo = document.createElement("input");
    campo.type = "number";
    campo.name = medida;
    campo.required = true;
    campo.step = ["repeticiones", "duracion"].includes(medida) ? "1" : "0.01";
    campo.min = medida === "carga" ? "0" : (["repeticiones", "duracion"].includes(medida) ? "1" : "0.01");
    campo.value = String((medida === "repeticiones" ? ejercicio.objetivos.repeticiones_minimas : (ejercicio.objetivos[medida] ?? (medida === "carga" ? ejercicio.carga_anterior?.carga : null))) ?? "");
    etiqueta.append(campo);
    formulario.append(etiqueta);
  }
  const etiquetaRir = document.createElement("label");
  etiquetaRir.textContent = `RIR opcional de ${ejercicio.nombre} (0 a 10)`;
  const campoRir = document.createElement("input");
  campoRir.type = "number";
  campoRir.name = "rir";
  campoRir.min = "0";
  campoRir.max = "10";
  campoRir.step = "1";
  etiquetaRir.append(campoRir);
  formulario.append(etiquetaRir);
  const guardar = document.createElement("button");
  guardar.type = "submit";
  guardar.textContent = "Registrar serie";
  guardar.setAttribute("aria-label", `Registrar serie de ${ejercicio.nombre}`);
  formulario.append(guardar);
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    if (cargando || control.actual) return;
    try {
      if (!formulario.reportValidity()) throw new Error("Revisá las medidas del ejercicio antes de registrar la serie.");
      const medidas = prepararMedidas(ejercicio.medidas_aplicables, Object.fromEntries(new FormData(formulario)));
      control.preparar(`/api/entrenamiento/sesiones/${sesionId}/series`, { ejercicio_planificado_id: ejercicio.id, ...medidas });
      enviar();
    } catch (error) { $("[data-error]").textContent = error.message; }
  });
  tarjeta.append(formulario);
}

function dibujarRegistro() {
  $("[data-registro]").hidden = !sesionActual;
  $("[data-series]").replaceChildren();
  if (!sesionActual) return;
  $("[data-sin-series]").hidden = sesionActual.series.length !== 0;
  for (const serie of sesionActual.series) {
    const ejercicio = sesionActual.ejercicios.find((e) => e.id === serie.ejercicio_planificado_id);
    const fila = document.createElement("li");
    fila.textContent = `${ejercicio.nombre} · ${describirObjetivos({ series: 1, ...serie })}${serie.rir === null ? "" : ` · RIR ${serie.rir}`}`;
    $("[data-series]").append(fila);
  }
}

function describirObjetivos(objetivos) {
  const partes = [`${objetivos.series} ${objetivos.series === 1 ? "serie" : "series"}`];
  if (objetivos.repeticiones_minimas != null) partes.push(`${objetivos.repeticiones_minimas}–${objetivos.repeticiones_maximas} reps`);
  if (objetivos.repeticiones != null) partes.push(`${objetivos.repeticiones} repeticiones`);
  if (objetivos.carga !== null) partes.push(formatearCarga(objetivos.carga));
  if (objetivos.duracion !== null) partes.push(`${objetivos.duracion} s`);
  if (objetivos.distancia !== null) partes.push(`${numero.format(Number(objetivos.distancia))} m`);
  return partes.join(" · ");
}

function dibujar(propuesta) {
  const coincide = Boolean(sesionActual && sesionActual.sesion_realizada.sesion_planificada_id === propuesta.sesion_planificada?.id);
  $("[data-iniciar]").hidden = !propuesta.sesion_planificada || coincide;
  $("[data-sesion-actual]").hidden = !coincide;
  $("[data-contenido]").dataset.versionReglas = propuesta.version_reglas;
  $("[data-fecha]").textContent = formatearFecha(propuesta.fecha_local);
  $("[data-explicacion]").replaceChildren();
  for (const razon of propuesta.explicacion.filter((r) => !r.datos.ejercicio_id)) {
    const texto = document.createElement("li");
    texto.textContent = razon.datos.explicacion;
    $("[data-explicacion]").append(texto);
  }
  $("[data-ejercicios]").replaceChildren();
  $("[data-titulo-sesion]").textContent = propuesta.sesion_planificada?.nombre
    ?? (propuesta.explicacion[0]?.regla === "sin_programa" ? "Sin programa de entrenamiento" : "Secuencia realizada");
  for (const propuesto of propuesta.ejercicios) {
    const ejercicio = coincide
      ? { ...propuesto, carga_anterior: sesionActual.ejercicios.find((e) => e.id === propuesto.id)?.carga_anterior ?? null }
      : propuesto;
    const tarjeta = document.createElement("li");
    tarjeta.className = "tarjeta";
    tarjeta.dataset.ejercicio = ejercicio.id;
    const nombre = document.createElement("h3");
    nombre.textContent = ejercicio.nombre;
    const objetivos = document.createElement("p");
    objetivos.textContent = describirObjetivos(ejercicio.objetivos);
    const pendiente = document.createElement("p");
    pendiente.textContent = `Series realizadas: ${ejercicio.realizado} · Pendientes: ${ejercicio.pendiente}`;
    const anterior = document.createElement("p");
    anterior.textContent = ejercicio.carga_anterior
      ? `Carga anterior: ${ejercicio.carga_anterior.carga == null ? "sin carga" : formatearCarga(ejercicio.carga_anterior.carga)} · ${ejercicio.carga_anterior.repeticiones ?? "sin"} repeticiones · ${formatearFecha(ejercicio.carga_anterior.fecha_local)}`
      : "Sin carga anterior.";
    tarjeta.append(nombre, objetivos, anterior, pendiente);
    const explicacion = document.createElement("ul");
    explicacion.dataset.ajuste = ejercicio.id;
    for (const razon of ejercicio.explicacion ?? []) {
      const texto = document.createElement("li");
      texto.textContent = razon.datos.explicacion;
      explicacion.append(texto);
    }
    tarjeta.append(explicacion);
    if (coincide && ejercicio.pendiente > 0) agregarFormulario(tarjeta, ejercicio);
    $("[data-ejercicios]").append(tarjeta);
  }
  $("[data-contenido]").hidden = false;
  dibujarRegistro();
}

async function actualizar(mensaje) {
  if (!autorizada || cargando || control.enCurso) return;
  cargando = true;
  actualizarBotones();
  if (!control.actual) $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando tu propuesta…";
  try {
    const [propuesta, realizada] = await Promise.all([
      llamarApi("/api/entrenamiento/propuesta"),
      sesionId ? llamarApi(`/api/entrenamiento/sesiones/${encodeURIComponent(sesionId)}`) : Promise.resolve(null),
    ]);
    propuestaActual = propuesta;
    sesionActual = realizada;
    dibujar(propuesta);
    $("[data-estado]").textContent = mensaje ?? "Propuesta actualizada.";
  } catch (error) {
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = `${mensaje ? mensaje + " " : ""}No se pudo cargar la propuesta. Podés actualizar para reintentar.`;
    $("[data-contenido]").hidden = true;
    $("[data-registro]").hidden = true;
  } finally {
    cargando = false;
    actualizarBotones();
  }
}

async function enviar() {
  if (cargando) return;
  const operacion = control.comenzar();
  if (!operacion) return;
  actualizarBotones();
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Registrando…";
  try {
    const datos = await llamarApi(operacion.ruta, { metodo: "POST", cuerpo: operacion.cuerpo, clave: operacion.clave });
    if (datos.sesion_realizada) {
      sesionId = datos.sesion_realizada.id;
      const enlace = new URL(location.href);
      enlace.search = "";
      enlace.searchParams.set("sesion", sesionId);
      history.replaceState(null, "", enlace);
    }
    if (datos.serie_realizada) {
      const ejercicio = sesionActual?.ejercicios.find((e) => e.id === datos.serie_realizada.ejercicio_planificado_id);
      if (ejercicio?.objetivos.descanso != null) {
        descanso = crearDescanso(ejercicio.objetivos.descanso, reloj.ahora());
        dibujarDescanso();
      }
    }
    control.finalizar();
    await actualizar(datos.sesion_realizada ? "Sesión realizada iniciada." : "Serie guardada.");
    const foco = document.querySelector("[data-serie] input") ?? $("[data-actualizar]");
    foco.focus();
  } catch (error) {
    control.finalizar(error);
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = control.actual
      ? "No se confirmó la operación. Podés reintentar o descartar el reintento."
      : "No se pudo registrar la operación.";
  } finally { actualizarBotones(); }
}

async function iniciar() {
  try {
    const [{ usuario }, estado] = await Promise.all([llamarApi("/api/sesion"), llamarApi("/api/estado")]);
    $("[data-demo]").hidden = !estado.modo_demo;
    if (usuario?.rol !== "socio") {
      $("[data-estado]").textContent = "Ingresá como socio desde el inicio para consultar tu entrenamiento.";
      return;
    }
    autorizada = true;
    await actualizar();
  } catch (error) {
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = "No se pudo cargar el entrenamiento. Podés actualizar para reintentar.";
  }
}
$("[data-actualizar]").addEventListener("click", () => autorizada ? actualizar() : iniciar());
$("[data-iniciar]").addEventListener("click", () => {
  if (cargando || control.actual || !propuestaActual?.sesion_planificada) return;
  control.preparar("/api/entrenamiento/sesiones", { sesion_planificada_id: propuestaActual.sesion_planificada.id });
  enviar();
});
$("[data-reintentar]").addEventListener("click", enviar);
$("[data-descartar]").addEventListener("click", () => {
  control.descartar();
  $("[data-estado]").textContent = "Reintento descartado. Actualizá para consultar las series guardadas.";
  actualizarBotones();
});
$("[data-cerrar]").addEventListener("click", async () => {
  if (control.actual) {
    $("[data-error]").textContent = "Reintentá o descartá la operación pendiente antes de cerrar sesión.";
    return;
  }
  try { await cerrarSesion(llamarApi); location.assign("/"); }
  catch (error) { $("[data-error]").textContent = error.message; }
});
$("[data-saltear]").addEventListener("click", () => { descanso?.saltear(reloj.ahora()); dibujarDescanso(); });
$("[data-sumar-descanso]").addEventListener("click", () => { descanso?.sumar30(reloj.ahora()); dibujarDescanso(); });
iniciar();
