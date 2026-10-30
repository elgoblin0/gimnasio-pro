import { actualizarMejoresHorarios } from "@comun/horarios.js";
import { llamarApi } from "@comun/api.js";
import { formatearCedula, formatearFechaHora } from "@comun/formatos.js";
import { crearControlDeOperacion, cerrarSesion } from "@comun/operaciones.js";
import { registrarPwa } from "@comun/pwa.js";

import { crearSondeo } from "@comun/sondeo.js";

registrarPwa();
let sondeos = [];
let escena;
let visitasEscena = [];
let zonaElegida;
let escenaIniciada = false;

function seleccionarVisita(visita) {
  if (escena) escena.elegirVisita(visita.id);
  else abrirTarjeta(visita.socio_id);
}

function actualizarPorZona() {
  for (const fila of document.querySelectorAll('[data-zona-sede]')) {
    const clave = fila.dataset.zonaSede;
    const nombre = fila.querySelector('progress').getAttribute('aria-label');
    let boton = fila.querySelector('[data-elegir-zona]');
    if (!boton) {
      boton = document.createElement('button');
      boton.type = 'button';
      boton.dataset.elegirZona = clave;
      boton.textContent = nombre;
      boton.addEventListener('click', () => {
        zonaElegida = zonaElegida === clave ? null : clave;
        escena?.abrirZona(zonaElegida ? nombre : null);
        actualizarPorZona();
      });
      fila.prepend(boton);
      fila.append(document.createElement('ul'));
    }
    boton.setAttribute('aria-expanded', String(zonaElegida === clave));
    const lista = fila.querySelector('ul');
    lista.hidden = zonaElegida !== clave;
    const foco = lista.contains(document.activeElement) ? document.activeElement.dataset.visitaZona : null;
    const conocidas = [...document.querySelectorAll('[data-zona-sede]')].map(f => f.dataset.zonaSede);
    lista.replaceChildren(...visitasEscena.filter(v => (conocidas.includes(v.zona) ? v.zona : 'en_la_sede') === clave).map(v => {
      const elemento = document.createElement('li');
      const elegir = document.createElement('button');
      elegir.type = 'button';
      elegir.dataset.visitaZona = v.id;
      elegir.textContent = `${v.nombre} · ${v.minutos} min${v.simulada ? ' · Visita simulada' : ''}${v.por_conciliar ? ' · Por conciliar' : ''}`;
      elegir.addEventListener('click', () => seleccionarVisita(v));
      elemento.append(elegir);
      return elemento;
    }));
    if (foco) [...lista.querySelectorAll('button')].find(b => b.dataset.visitaZona === foco)?.focus();
  }
}

async function iniciarEscena() {
  if (escenaIniciada) return;
  escenaIniciada = true;
  try {
    const {crearEscena} = await import('@escena');
    escena = crearEscena($('[data-escena-ocupacion]'), visita => abrirTarjeta(visita.socio_id));
    escena.actualizar(visitasEscena);
    $('[data-escena-ocupacion]').dataset.lista = 'true';
  } catch {
    $('[data-escena-ocupacion]').hidden = true;
    $('[data-alternativa-escena]').hidden = false;
  }
}
function dibujarOcupacion(ocupacion) {
  sedeId = ocupacion.sede_id;
  $("[data-ocupacion]").textContent = `${ocupacion.ocupacion_registrada} de ${ocupacion.aforo_maximo}`;
  for (const barra of document.querySelectorAll("[data-zona-sede]")) {
    const cantidad = ocupacion.por_zona[barra.dataset.zonaSede];
    barra.querySelector("progress").max = Math.max(1, ocupacion.ocupacion_registrada);
    barra.querySelector("progress").value = cantidad;
    barra.querySelector("span").textContent = cantidad;
  }
}
const $ = (selector) => document.querySelector(selector);
const control = crearControlDeOperacion();
let sedeId;
let autorizada = false;
let cargando = false;
let visitaConciliada;

function actualizarBotones() {
  for (const elemento of document.querySelectorAll("[data-entrada] button, [data-entrada] select, [data-salida]")) {
    elemento.disabled = Boolean(control.actual) || cargando;
  }
  const pendiente = Boolean(control.actual);
  for (const selector of ["#salida-en", "#motivo", "[data-confirmar-conciliacion]"]) {
    $(selector).disabled = pendiente || cargando;
  }
  $("[data-cancelar-conciliacion]").disabled = pendiente;
  $("[data-reintentar-conciliacion]").hidden = !pendiente;
  $("[data-reintentar-conciliacion]").disabled = control.enCurso || cargando;
  $("[data-descartar-conciliacion]").hidden = !pendiente;
  $("[data-descartar-conciliacion]").disabled = control.enCurso;
  $("[data-reintento]").hidden = !control.actual || control.enCurso;
  $("[data-reintentar]").disabled = control.enCurso || cargando;
  $("[data-descartar]").disabled = control.enCurso;
}

function dibujarVisitas(visitas) {
  visitasEscena = visitas;
  actualizarPorZona();
  escena?.actualizar(visitas);
  $("[data-visitas]").replaceChildren();
  $("[data-vacio]").hidden = visitas.length !== 0;
  for (const visita of visitas) {
    const tarjeta = document.createElement("li");
    tarjeta.className = "tarjeta";
    const titulo = document.createElement("h3");
    titulo.textContent = visita.nombre;
    const detalle = document.createElement("p");
    const habitual = visita.permanencia_habitual;
    const permanencia = habitual.suficiente
      ? `suele quedarse ${habitual.mediana} min`
      : `datos insuficientes (${habitual.observaciones} visitas)`;
    detalle.textContent = `Cédula ${formatearCedula(visita.cedula)} · Entrada ${formatearFechaHora(visita.entrada)} · lleva ${visita.minutos} min · ${permanencia}`;
    const boton = document.createElement("button");
    boton.type = "button";
    boton.dataset.salida = visita.id;
    boton.textContent = "Registrar salida";
    boton.setAttribute("aria-label", `Registrar salida de ${visita.nombre}`);
    boton.addEventListener("click", () => {
      if (control.actual || cargando) return;
      control.preparar("/api/salidas", { entrada_id: visita.id });
      enviar();
    });
    tarjeta.append(titulo, detalle);
    if (visita.simulada) {
      const marca = document.createElement("strong");
      marca.textContent = "simulada";
      tarjeta.append(marca);
    }
    const verTarjeta = document.createElement("button");
    verTarjeta.type = "button";
    verTarjeta.textContent = "Ver tarjeta contextual";
    verTarjeta.setAttribute("aria-label", `Ver tarjeta contextual de ${visita.nombre}`);
    verTarjeta.addEventListener("click", () => seleccionarVisita(visita));
    tarjeta.append(verTarjeta);
    if (visita.por_conciliar) {
      const marca = document.createElement("strong");
      marca.className = "por-conciliar";
      marca.textContent = "por conciliar";
      tarjeta.append(marca);
      const conciliar = document.createElement("button");
      conciliar.type = "button";
      conciliar.dataset.salida = visita.id;
      conciliar.textContent = "Conciliar salida";
      conciliar.addEventListener("click", () => abrirConciliacion(visita));
      tarjeta.append(conciliar);
    }
    tarjeta.append(boton);
    $("[data-visitas]").append(tarjeta);
  }
}

async function actualizar() {
  if (!autorizada || cargando || control.enCurso) return;
  cargando = true;
  actualizarMejoresHorarios();
  actualizarBotones();
  try {
    const [ocupacion, { visitas }, { socios }] = await Promise.all([
      llamarApi("/api/ocupacion"), llamarApi("/api/visitas?abiertas=1"), llamarApi("/api/visitas/socios"),
    ]);
    dibujarOcupacion(ocupacion);
    const seleccion = $("#socio").value;
    $("#socio").replaceChildren(new Option("Elegí un socio", ""), ...socios.map((socio) =>
      new Option(`${socio.nombre} · ${formatearCedula(socio.cedula)}`, socio.id)));
    $("#socio").value = seleccion;
    dibujarVisitas(visitas);
    $("[data-contenido]").hidden = false;
    return true;
  } catch (error) {
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = "No se pudieron actualizar las visitas. Podés reintentar.";
    return false;
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
    sondeos.forEach((sondeo) => sondeo.invalidar());
    dibujarOcupacion(datos.ocupacion);
    dibujarVisitas(datos.visitas);
    control.finalizar();
    if (operacion.ruta.endsWith("/conciliacion")) $("[data-conciliacion]").close();
    $("[data-estado]").textContent = operacion.ruta === "/api/entradas" ? "Entrada registrada." : "Salida registrada.";
    $("#socio").focus();
    if (operacion.ruta === "/api/entradas") abrirTarjeta(operacion.cuerpo.socio_id);
    else if ($("[data-tarjeta-contextual]").open) await abrirTarjeta(socioTarjeta, false);
  } catch (error) {
    control.finalizar(error);
    $("[data-error]").textContent = error.message;
    if (operacion.ruta.endsWith("/conciliacion")) $("[data-error-conciliacion]").textContent = error.message;
    $("[data-estado]").textContent = control.actual ? "No se confirmó la operación. Podés reintentar o descartar el reintento." : "La operación fue rechazada.";
  } finally {
    actualizarBotones();
  }
}

let consultaTarjeta = 0;
let focoAnteriorTarjeta;
let socioTarjeta;
async function abrirTarjeta(socioId, enfocar = true) {
  socioTarjeta = socioId;
  const consulta = ++consultaTarjeta;
  const panel = $("[data-tarjeta-contextual]");
  $("[data-tarjeta-datos]").textContent = "Cargando tarjeta contextual…";
  if (!panel.open) {
    focoAnteriorTarjeta = document.activeElement;
    panel.show();
  }
  if (enfocar) $("[data-cerrar-tarjeta]").focus();
  try {
    const datos = await llamarApi(`/api/socios/${socioId}/tarjeta`);
    if (consulta !== consultaTarjeta || !panel.open) return;
    const contenido = $("[data-tarjeta-datos]");
    contenido.replaceChildren();
    const agregar = (texto, clase = "") => {
      const parrafo = document.createElement("p");
      parrafo.textContent = texto;
      parrafo.className = clase;
      contenido.append(parrafo);
    };
    if (datos.socio.simulada) agregar("Socio simulado de la demo");
    agregar(`${datos.socio.nombre} ${datos.socio.apellido} · Cédula ${datos.socio.cedula}`);
    const membresia = datos.membresia;
    if (membresia) {
      const estado = !membresia.vigente ? "vencida" : membresia.dias_restantes <= 7 ? "por vencer" : "vigente";
      const hasta = membresia.hasta.split("-").reverse().join("/");
      agregar(`Membresía ${estado} · hasta ${hasta} · ${membresia.dias_restantes} días restantes`, `membresia-${estado.replaceAll(" ", "-")}`);
    } else agregar("Sin membresía iniciada.");
    if (datos.visita_abierta) agregar(`Visita abierta desde ${formatearFechaHora(datos.visita_abierta.desde)} · ${datos.visita_abierta.minutos} min`);
    else if (datos.ultima_visita) agregar(`Última visita: ${formatearFechaHora(datos.ultima_visita.desde)} a ${formatearFechaHora(datos.ultima_visita.hasta)}`);
    else agregar("Sin visitas registradas.");
    agregar(`Visitas de las últimas cuatro semanas: ${datos.visitas_ultimas_4_semanas}`);
    const habitual = datos.permanencia_habitual;
    agregar(habitual.suficiente ? `Permanencia habitual: ${habitual.mediana} min` : `Permanencia habitual: datos insuficientes (${habitual.observaciones} visitas)`);
  } catch (error) {
    if (consulta === consultaTarjeta && panel.open) $("[data-tarjeta-datos]").textContent = error.message;
  }
}
$("[data-cerrar-tarjeta]").addEventListener("click", () => $("[data-tarjeta-contextual]").close());
$("[data-tarjeta-contextual]").addEventListener("close", () => {
  (focoAnteriorTarjeta?.isConnected ? focoAnteriorTarjeta : $("#socio")).focus();
});
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape" && $("[data-tarjeta-contextual]").open) {
    $("[data-tarjeta-contextual]").close();
  }
});

function abrirConciliacion(visita) {
  if (control.actual || cargando) return;
  visitaConciliada = visita;
  const habitual = visita.permanencia_habitual_sede;
  // Conservar la hora de la sede, independientemente de la zona del navegador.
  const fecha = new Date(visita.entrada_local.slice(0, 19) + "Z");
  fecha.setUTCMinutes(fecha.getUTCMinutes() + (habitual.suficiente ? habitual.mediana : 60));
  $("#salida-en").value = fecha.toISOString().slice(0, 16);
  $("#motivo").value = "";
  $("[data-error-conciliacion]").textContent = "";
  actualizarBotones();
  $("[data-conciliacion]").showModal();
}

$("[data-formulario-conciliacion]").addEventListener("submit", (evento) => {
  evento.preventDefault();
  if (control.actual || cargando) return;
  const desplazamiento = visitaConciliada.entrada_local.slice(-6);
  control.preparar(`/api/visitas/${visitaConciliada.id}/conciliacion`, {
    salida_en: $("#salida-en").value + desplazamiento, motivo: $("#motivo").value,
  });
  enviar();
});
$("[data-conciliacion]").addEventListener("cancel", (evento) => {
  if (control.actual) evento.preventDefault();
});
$("[data-cancelar-conciliacion]").addEventListener("click", () => $("[data-conciliacion]").close());
$("[data-reintentar-conciliacion]").addEventListener("click", enviar);
$("[data-descartar-conciliacion]").addEventListener("click", () => {
  control.descartar();
  actualizarBotones();
});

$("[data-entrada]").addEventListener("submit", (evento) => {
  evento.preventDefault();
  if (control.actual || cargando || !$("#socio").value || !sedeId) return;
  control.preparar("/api/entradas", { socio_id: $("#socio").value, sede_id: sedeId });
  enviar();
});
$("[data-reintentar]").addEventListener("click", enviar);
$("[data-descartar]").addEventListener("click", () => {
  control.descartar();
  $("[data-estado]").textContent = "Reintento descartado. Actualizá las visitas para consultar el registro.";
  actualizarBotones();
});
$("[data-actualizar]").addEventListener("click", () => autorizada ? actualizar() : iniciar());
window.addEventListener("focus", actualizar);
$("[data-cerrar]").addEventListener("click", async () => {
  if (control.actual) {
    $("[data-error]").textContent = "Reintentá o descartá la operación pendiente antes de cerrar sesión.";
    return;
  }
  try { await cerrarSesion(llamarApi); location.assign("/"); }
  catch (error) { $("[data-error]").textContent = error.message; }
});

async function iniciar() {
  try {
    const [{ usuario }, estado] = await Promise.all([llamarApi("/api/sesion"), llamarApi("/api/estado")]);
    $("[data-demo]").hidden = !estado.modo_demo;
    if (usuario?.rol !== "recepcion") {
      $("[data-estado]").textContent = "Ingresá como recepción desde el inicio para registrar visitas.";
      return;
    }
    autorizada = true;
    iniciarEscena();
    if (!sondeos.length) sondeos = [
      crearSondeo({ url: "/api/ocupacion", alCambiar: dibujarOcupacion }),
      crearSondeo({ url: "/api/visitas?abiertas=1", alCambiar: ({ visitas }) => { dibujarVisitas(visitas); actualizarBotones(); } }),
    ];
    if (await actualizar()) $("[data-estado]").textContent = "Recepción lista.";
  } catch (error) { $("[data-error]").textContent = error.message; }
}
iniciar();
