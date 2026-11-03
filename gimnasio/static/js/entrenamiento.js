import { actualizarMejoresHorarios } from "@comun/horarios.js";
import { llamarApi } from "@comun/api.js";
import { formatearCarga, formatearFecha } from "@comun/formatos.js";
import { cerrarSesion, crearControlDeOperacion } from "@comun/operaciones.js";
import { prepararMedidas } from "@comun/series.js";
import { registrarPwa } from "@comun/pwa.js";
import { modoSinEfectos } from "@comun/efectos.js";
import { crearSelectorZonas } from "@comun/zonas.js";

import { crearDescanso } from "@comun/descanso.js";
import { crearReloj } from "@comun/reloj.js";
import { avanceDeSesion, describirObjetivos, ejercicioEnFoco, estadoDelDia, mensajeDeOperacion, razonesVisibles, seQuito, sinTrabajoHoy } from "./entrenamiento-textos.js";

const $ = (selector) => document.querySelector(selector);
import { crearSondeo } from "@comun/sondeo.js";
registrarPwa();
let sondeoOcupacion;
const reloj = crearReloj();
let descanso = null;
let descansoTotal = 1;
function dibujarDescanso() {
  if (!descanso) return;
  const estado = descanso.consultar(reloj.ahora());
  descansoTotal = Math.max(descansoTotal, estado.restantes);
  $("[data-descanso]").hidden = false;
  $("[data-descanso]").toggleAttribute("data-terminado", estado.terminado);
  $("[data-restantes]").textContent = `${estado.restantes} s`;
  $("[data-descanso-barra]").style.transform = `scaleX(${estado.restantes / descansoTotal})`;
  const anuncio = estado.terminado ? "Descanso terminado." : "";
  if ($("[data-descanso-anuncio]").textContent !== anuncio) $("[data-descanso-anuncio]").textContent = anuncio;
}
setInterval(dibujarDescanso, 250);
let chequeoResuelto = Boolean(new URL(location.href).searchParams.get("sesion"));
let autorizada = false;
let cargando = false;
let propuestaActual = null;
let sesionActual = null;
let sesionId = new URL(location.href).searchParams.get("sesion");
let avisando = false;
let elegido = null;
let otraSesion = false;
let ultimaPropuesta = null;
const control = crearControlDeOperacion();
const zonasChequeo = crearSelectorZonas($("[data-zonas-chequeo]"));
const selectoresDolor = new Set();
const numero = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });

function actualizarBotones() {
  $("[data-terminar]").disabled = cargando || Boolean(control.actual);
  zonasChequeo.deshabilitar(Boolean(control.actual) || cargando);
  for (const selector of selectoresDolor) selector.deshabilitar(Boolean(control.actual) || cargando);
  for (const elemento of document.querySelectorAll("[data-formulario-chequeo] input, [data-formulario-chequeo] button, [data-iniciar], [data-avisar-entrenador], [data-serie] input, [data-serie] button, [data-sustitucion] button, [data-dolor] button")) {
    elemento.disabled = Boolean(control.actual) || cargando || (elemento.matches("[data-iniciar], [data-avisar-entrenador]") && !chequeoResuelto);
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
    etiqueta.textContent = etiquetas[medida];
    const campo = document.createElement("input");
    campo.setAttribute("aria-label", `${etiquetas[medida]} de ${ejercicio.nombre}`);
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
  etiquetaRir.textContent = "RIR opcional";
  const campoRir = document.createElement("input");
  campoRir.setAttribute("aria-label", `RIR opcional de ${ejercicio.nombre} (0 a 10)`);
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
      control.preparar(`/api/entrenamiento/sesiones/${sesionId}/series`, { ejercicio_planificado_id: ejercicio.id, ...(ejercicio.sustitucion ? { ejercicio_hecho_id: ejercicio.sustitucion.ejercicio_hecho_id } : {}), ...medidas });
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
    const fila = document.createElement("li");
    fila.textContent = `${serie.ejercicio_hecho_nombre} · ${describirObjetivos({ series: 1, ...serie })}${serie.rir === null ? "" : ` · RIR ${serie.rir}`}`;
    $("[data-series]").append(fila);
  }
}

// La sesión abierta sin nada que hacer ya dejó su aviso: no hay series para registrar ni sesión para terminar.
const abiertaSinTrabajo = (realizada) => Boolean(realizada) && !realizada.series.length && sinTrabajoHoy(realizada.ejercicios);

function dibujar(propuesta) {
  const coincide = Boolean(sesionActual && sesionActual.sesion_realizada.sesion_planificada_id === propuesta.sesion_planificada?.id);
  // Sin freno no nace ningún aviso: un equipo fuera de servicio no llega acá.
  const sinTrabajo = Boolean(propuesta.sesion_planificada) && sinTrabajoHoy(propuesta.ejercicios) && propuesta.frenos.length > 0;
  const avisado = abiertaSinTrabajo(sesionActual);
  const enVivo = coincide && !avisado;
  const foco = enVivo ? ejercicioEnFoco(propuesta.ejercicios, elegido) : null;
  ultimaPropuesta = propuesta;
  document.body.toggleAttribute("data-sesion-en-vivo", enVivo);
  $("[data-en-vivo]").hidden = !enVivo;
  if (enVivo) {
    const avance = avanceDeSesion(propuesta.ejercicios);
    $("[data-avance]").textContent = avance.texto;
    $("[data-avance-barra]").max = Math.max(1, avance.total);
    $("[data-avance-barra]").value = avance.hechas;
    const cabecera = $(".cabecera");
    $("[data-en-vivo]").style.top = getComputedStyle(cabecera).position === "sticky" ? `${cabecera.offsetHeight}px` : "0";
  }
  $("[data-iniciar]").hidden = !propuesta.sesion_planificada || coincide || sinTrabajo;
  $("[data-sesion-actual]").hidden = !coincide || avisado;
  $("[data-sin-trabajo]").hidden = !sinTrabajo;
  $("[data-sin-trabajo-texto]").textContent = avisado
    ? "Tu entrenador ya tiene el aviso. Hoy no hace falta registrar nada."
    : "Hoy no hay ejercicios que puedas hacer con seguridad. Avisale a tu entrenador para que ajuste tu programa.";
  $("[data-avisar-entrenador]").hidden = avisado;
  $("[data-contenido]").dataset.versionReglas = propuesta.version_reglas;
  $("[data-fecha]").textContent = formatearFecha(propuesta.fecha_local);
  $("[data-explicacion]").replaceChildren();
  for (const razon of propuesta.explicacion.filter((r) => !r.datos.ejercicio_id)) {
    const texto = document.createElement("li");
    texto.textContent = razon.regla === "secuencia_realizada"
      ? "Terminaste tu programa; tu entrenador prepara el siguiente"
      : razon.datos.explicacion;
    $("[data-explicacion]").append(texto);
  }
  $("[data-ejercicios]").replaceChildren();
  selectoresDolor.clear();
  $("[data-titulo-sesion]").textContent = propuesta.sesion_planificada?.nombre
    ?? (propuesta.explicacion[0]?.regla === "sin_programa" ? "Sin programa de entrenamiento" : "Secuencia realizada");
  for (const propuesto of propuesta.ejercicios) {
    const ejercicio = coincide
      ? { ...propuesto, carga_anterior: sesionActual.ejercicios.find((e) => e.id === propuesto.id)?.carga_anterior ?? null, ...sesionActual.sustituciones?.[propuesto.id] }
      : propuesto;
    const tarjeta = document.createElement("li");
    tarjeta.className = "tarjeta";
    tarjeta.dataset.ejercicio = ejercicio.id;
    const nombre = document.createElement("h3");
    nombre.textContent = ejercicio.nombre + (ejercicio.no_disponible ? " · No disponible" : "");
    const objetivos = document.createElement("p");
    objetivos.className = "ejercicio-objetivos";
    objetivos.textContent = seQuito(ejercicio) ? "Quitado por hoy" : describirObjetivos(ejercicio.objetivos);
    const pendiente = document.createElement("p");
    pendiente.className = "ejercicio-dato";
    pendiente.textContent = `Series realizadas: ${ejercicio.realizado} · Pendientes: ${ejercicio.pendiente}`;
    const anterior = document.createElement("p");
    anterior.className = "ejercicio-dato";
    anterior.textContent = ejercicio.carga_anterior
      ? `Carga anterior: ${ejercicio.carga_anterior.carga == null ? "sin carga" : formatearCarga(ejercicio.carga_anterior.carga)} · ${ejercicio.carga_anterior.repeticiones ?? "sin"} repeticiones · ${formatearFecha(ejercicio.carga_anterior.fecha_local)}`
      : "Sin carga anterior.";
    const cuerpo = document.createElement("div");
    cuerpo.className = "ejercicio-cuerpo";
    tarjeta.append(nombre, objetivos);
    if (enVivo && ejercicio.id === foco) {
      tarjeta.dataset.foco = "";
      tarjeta.append(marcasDeSeries(ejercicio));
    } else if (enVivo) {
      tarjeta.dataset.plegada = "";
      cuerpo.hidden = true;
      tarjeta.append(accionDePlegada(ejercicio));
    }
    if (!seQuito(ejercicio)) cuerpo.append(anterior, pendiente);
    const explicacion = document.createElement("ul");
    explicacion.className = "ejercicio-porque";
    explicacion.dataset.ajuste = ejercicio.id;
    for (const razon of razonesVisibles(ejercicio)) {
      const texto = document.createElement("li");
      // Tras un borrado de datos de salud, la razón guardada conserva la regla y no el texto.
      texto.textContent = razon.datos.explicacion ?? "Se aplicó un freno de seguridad.";
      explicacion.append(texto);
    }
    cuerpo.append(explicacion);
    tarjeta.append(cuerpo);
    if (coincide && ejercicio.pendiente > 0 && !ejercicio.no_disponible) {
      agregarFormulario(cuerpo, ejercicio);
      const otras = document.createElement("div");
      otras.className = "ejercicio-otras";
      agregarSustitucion(otras, ejercicio);
      agregarDolor(otras, ejercicio);
      cuerpo.append(otras);
    }
    $("[data-ejercicios]").append(tarjeta);
  }
  $("[data-contenido]").hidden = false;
  dibujarRegistro();
  if (avisado) $("[data-registro]").hidden = true;
  actualizarBotones();
}

// El foco va al primer campo sin que el panel fijo tape el nombre del ejercicio.
function enfocarEjercicio() {
  const tarjeta = $("[data-foco]");
  const campo = tarjeta?.querySelector("[data-serie] input");
  if (!campo) return false;
  campo.focus({ preventScroll: true });
  tarjeta.style.scrollMarginTop = `${$("[data-en-vivo]").getBoundingClientRect().height + (parseInt($("[data-en-vivo]").style.top, 10) || 0) + 8}px`;
  tarjeta.scrollIntoView({ block: "start" });
  return true;
}

function marcasDeSeries(ejercicio) {
  const marcas = document.createElement("div");
  marcas.className = "ejercicio-marcas";
  marcas.setAttribute("aria-hidden", "true");
  for (let indice = 0; indice < ejercicio.realizado + ejercicio.pendiente; indice += 1) {
    const marca = document.createElement("span");
    if (indice < ejercicio.realizado) marca.dataset.hecha = "";
    marcas.append(marca);
  }
  return marcas;
}

function accionDePlegada(ejercicio) {
  if (ejercicio.pendiente <= 0 || ejercicio.no_disponible || seQuito(ejercicio)) {
    const dato = document.createElement("p");
    dato.className = "ejercicio-dato";
    dato.textContent = ejercicio.pendiente <= 0 ? "Hecho" : "Hoy no";
    return dato;
  }
  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "boton-enlace";
  boton.dataset.focoEjercicio = ejercicio.id;
  boton.textContent = "Hacer ahora";
  boton.setAttribute("aria-label", `Hacer ahora ${ejercicio.nombre}`);
  boton.addEventListener("click", () => {
    elegido = ejercicio.id;
    dibujar(ultimaPropuesta);
    enfocarEjercicio();
  });
  return boton;
}

// El día ya tiene una sesión con series: se muestra eso en vez de proponer otra, salvo que el socio la pida.
function dibujarDia(realizada) {
  const estado = estadoDelDia(realizada);
  $("[data-dia-titulo]").textContent = estado.titulo;
  $("[data-dia-texto]").textContent = estado.texto;
  $("[data-dia-seguir]").hidden = !estado.pendientes;
  $("[data-dia-seguir]").dataset.sesion = realizada.sesion_realizada.id;
  $("[data-dia-resumen]").dataset.sesion = realizada.sesion_realizada.id;
  $("[data-dia]").hidden = false;
  $("[data-contenido]").hidden = true;
  $("[data-registro]").hidden = true;
  $("[data-en-vivo]").hidden = true;
  document.body.removeAttribute("data-sesion-en-vivo");
}

async function actualizar(mensaje) {
  if (!autorizada || cargando || control.enCurso) return;
  cargando = true;
  actualizarMejoresHorarios();
  actualizarBotones();
  if (!control.actual) $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando tu propuesta…";
  try {
    const [propuesta, realizada, hoy] = await Promise.all([
      llamarApi("/api/entrenamiento/propuesta"),
      sesionId ? llamarApi(`/api/entrenamiento/sesiones/${encodeURIComponent(sesionId)}`) : Promise.resolve(null),
      llamarApi("/api/entrenamiento/hoy"),
    ]);
    propuestaActual = propuesta;
    sesionActual = realizada;
    if (hoy.chequeo) chequeoResuelto = true;
    const delDia = realizada ?? (hoy.sesion_realizada_id && !otraSesion
      ? await llamarApi(`/api/entrenamiento/sesiones/${encodeURIComponent(hoy.sesion_realizada_id)}`)
      : null);
    const diaVisible = !otraSesion && delDia?.series.length > 0 && (!realizada || !estadoDelDia(delDia).pendientes);
    $("[data-dia]").hidden = true;
    $("[data-chequeo]").hidden = chequeoResuelto || diaVisible;
    const efectiva = realizada?.ejercicios.some((e) => e.pendiente > 0) || abiertaSinTrabajo(realizada)
      ? realizada.prescripcion_efectiva : null;
    dibujar(efectiva ? {
      ...propuesta,
      ...efectiva,
      sesion_planificada: realizada.sesion_planificada,
      ejercicios: realizada.ejercicios,
    } : propuesta);
    if (diaVisible) dibujarDia(delDia);
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
  $("[data-record]").textContent = "";
  try {
    const datos = await llamarApi(operacion.ruta, { metodo: "POST", cuerpo: operacion.cuerpo, clave: operacion.clave });
    if (datos.chequeo) {
      chequeoResuelto = true;
      $("[data-chequeo]").hidden = true;
    }
    if (datos.sesion_realizada) {
      sesionId = datos.sesion_realizada.id;
      otraSesion = false;
      elegido = null;
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
    if (datos.records?.length) {
      const anuncio = $("[data-record]");
      anuncio.textContent = datos.records.map((record) => {
        const marca = record.medida === "carga_maxima"
          ? formatearCarga(record.marca)
          : `${numero.format(record.marca)} repeticiones a ${formatearCarga(record.carga)}`;
        return `Récord: ${marca} en ${record.ejercicio_hecho_nombre}`;
      }).join(". ");
      if (!modoSinEfectos().activo) {
        anuncio.animate([{ opacity: 0, transform: "scale(.94)" }, { opacity: 1, transform: "scale(1.03)", offset: .6 }, { opacity: 1, transform: "scale(1)" }], { duration: 480, easing: "ease-out" });
      }
    }
    control.finalizar();
    await actualizar(mensajeDeOperacion(datos, { avisando }));
    avisando = false;
    if (!enfocarEjercicio()) $("[data-actualizar]").focus();
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
    sondeoOcupacion ??= crearSondeo({ url: "/api/ocupacion", alCambiar: (datos) => {
      $("[data-ocupacion-ahora]").hidden = false;
      $("[data-ocupacion]").textContent = `${datos.ocupacion_registrada} de ${datos.aforo_maximo}`;
      const barra = $("[data-aforo]");
      barra.max = datos.aforo_maximo;
      barra.value = datos.ocupacion_registrada;
    } });
    await actualizar();
  } catch (error) {
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = "No se pudo cargar el entrenamiento. Podés actualizar para reintentar.";
  }
}
$("[data-actualizar]").addEventListener("click", () => autorizada ? actualizar() : iniciar());
$("[data-terminar]").addEventListener("click", () => {
  if (cargando || control.actual || !sesionId) return;
  location.assign(`/resumen-sesion.html?sesion=${encodeURIComponent(sesionId)}`);
});
$("[data-dia-resumen]").addEventListener("click", (evento) => {
  location.assign(`/resumen-sesion.html?sesion=${encodeURIComponent(evento.currentTarget.dataset.sesion)}`);
});
$("[data-dia-seguir]").addEventListener("click", (evento) => {
  location.assign(`/entrenamiento.html?sesion=${encodeURIComponent(evento.currentTarget.dataset.sesion)}`);
});
$("[data-otra-sesion]").addEventListener("click", () => {
  otraSesion = true;
  sesionId = null;
  history.replaceState(null, "", location.pathname);
  actualizar();
});
$("[data-iniciar]").addEventListener("click", () => {
  if (cargando || control.actual || !propuestaActual?.sesion_planificada) return;
  control.preparar("/api/entrenamiento/sesiones", { sesion_planificada_id: propuestaActual.sesion_planificada.id });
  enviar();
});
// El aviso al entrenador nace con la sesión realizada: abrirla es lo que lo deja en su bandeja.
$("[data-avisar-entrenador]").addEventListener("click", () => {
  if (cargando || control.actual || !propuestaActual?.sesion_planificada) return;
  avisando = true;
  control.preparar("/api/entrenamiento/sesiones", { sesion_planificada_id: propuestaActual.sesion_planificada.id });
  enviar();
});
$("[data-formulario-chequeo]").addEventListener("submit", (evento) => {
  evento.preventDefault();
  if (cargando || control.actual || !autorizada) return;
  const datos = new FormData(evento.currentTarget);
  control.preparar("/api/entrenamiento/chequeos", { sueno: Number(datos.get("sueno")), energia: Number(datos.get("energia")), zonas: zonasChequeo.zonas() });
  enviar();
});
$("[data-saltear-chequeo]").addEventListener("click", () => {
  if (cargando || control.actual) return;
  chequeoResuelto = true;
  $("[data-chequeo]").hidden = true;
  if (propuestaActual) dibujar(propuestaActual);
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


function agregarSustitucion(tarjeta, ejercicio) {
  const contenedor = document.createElement("div");
  contenedor.dataset.sustitucion = ejercicio.id;
  const boton = document.createElement("button");
  boton.type = "button";
  boton.textContent = "Máquina ocupada";
  boton.setAttribute("aria-label", `Máquina ocupada de ${ejercicio.nombre}`);
  boton.addEventListener("click", async () => {
    if (cargando || control.actual) return;
    boton.disabled = true;
    try {
      const datos = await llamarApi(`/api/entrenamiento/sesiones/${sesionId}/ejercicios/${ejercicio.id}/alternativas`);
      const lista = document.createElement("div");
      lista.setAttribute("role", "group");
      lista.setAttribute("aria-label", `Alternativas de ${ejercicio.nombre}`);
      const explicacion = document.createElement("p");
      explicacion.setAttribute("role", "status");
      explicacion.textContent = datos.explicacion?.datos.explicacion ?? "No hay alternativas compatibles.";
      lista.append(explicacion);
      for (const [indice, alternativa] of datos.alternativas.entries()) {
        const elegir = document.createElement("button");
        elegir.type = "button";
        elegir.textContent = `${indice === 0 ? "Propuesta: " : ""}${alternativa.nombre} · ${alternativa.equipo}`;
        if (indice === 0) elegir.className = "primario";
        elegir.addEventListener("click", () => {
          if (cargando || control.actual) return;
          control.preparar(`/api/entrenamiento/sesiones/${sesionId}/sustituciones`, {
            ejercicio_planificado_id: ejercicio.id, ejercicio_hecho_id: alternativa.ejercicio_id,
          });
          enviar();
        });
        lista.append(elegir);
      }
      contenedor.replaceChildren(boton, lista);
      lista.querySelector("button")?.focus();
    } catch (error) { $("[data-error]").textContent = error.message; }
    finally { actualizarBotones(); }
  });
  contenedor.append(boton);
  tarjeta.append(contenedor);
}

function agregarDolor(tarjeta, ejercicio) {
  const contenedor = document.createElement("div");
  contenedor.dataset.dolor = ejercicio.id;
  const boton = document.createElement("button");
  boton.type = "button";
  boton.textContent = "Me duele";
  boton.setAttribute("aria-label", `Me duele durante ${ejercicio.nombre}`);
  boton.addEventListener("click", () => {
    if (cargando || control.actual) return;
    if (contenedor.querySelector("form")) return;
    const formulario = document.createElement("form");
    const selector = crearSelectorZonas(formulario);
    selectoresDolor.add(selector);
    const guardar = document.createElement("button");
    guardar.type = "submit";
    guardar.textContent = "Guardar dolor reportado";
    formulario.append(guardar);
    formulario.addEventListener("submit", (evento) => {
      evento.preventDefault();
      if (cargando || control.actual) return;
      const zonas = selector.zonas();
      if (!zonas.length) { $("[data-error]").textContent = "Elegí al menos una zona con dolor."; return; }
      control.preparar(`/api/entrenamiento/sesiones/${sesionId}/dolores`, { ejercicio_planificado_id: ejercicio.id, zonas });
      enviar();
    });
    contenedor.append(formulario);
    formulario.querySelector("[role=checkbox]").focus();
  });
  contenedor.append(boton);
  tarjeta.append(contenedor);
}
