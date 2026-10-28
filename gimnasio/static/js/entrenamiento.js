import { llamarApi } from "@comun/api.js";
import { formatearCarga, formatearFecha } from "@comun/formatos.js";
import { cerrarSesion, crearControlDeOperacion } from "@comun/operaciones.js";
import { prepararMedidas } from "@comun/series.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
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
    campo.value = String((medida === "repeticiones" ? ejercicio.objetivos.repeticiones_minimas : ejercicio.objetivos[medida]) ?? "");
    etiqueta.append(campo);
    formulario.append(etiqueta);
  }
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
    fila.textContent = `${ejercicio.nombre} · ${describirObjetivos({ series: 1, ...serie })}`;
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
  for (const razon of propuesta.explicacion) {
    const texto = document.createElement("li");
    texto.textContent = razon.datos.explicacion;
    $("[data-explicacion]").append(texto);
  }
  $("[data-ejercicios]").replaceChildren();
  $("[data-titulo-sesion]").textContent = propuesta.sesion_planificada?.nombre
    ?? (propuesta.explicacion[0]?.regla === "sin_programa" ? "Sin programa de entrenamiento" : "Secuencia realizada");
  for (const ejercicio of propuesta.ejercicios) {
    const tarjeta = document.createElement("li");
    tarjeta.className = "tarjeta";
    tarjeta.dataset.ejercicio = ejercicio.id;
    const nombre = document.createElement("h3");
    nombre.textContent = ejercicio.nombre;
    const objetivos = document.createElement("p");
    objetivos.textContent = describirObjetivos(ejercicio.objetivos);
    const pendiente = document.createElement("p");
    pendiente.textContent = `Series realizadas: ${ejercicio.realizado} · Pendientes: ${ejercicio.pendiente}`;
    tarjeta.append(nombre, objetivos, pendiente);
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
iniciar();
