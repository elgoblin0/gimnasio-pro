import { llamarApi } from "@comun/api.js";
import { formatearCedula, formatearFechaHora } from "@comun/formatos.js";
import { crearControlDeOperacion, cerrarSesion } from "@comun/operaciones.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
const control = crearControlDeOperacion();
let sedeId;
let autorizada = false;
let cargando = false;

function actualizarBotones() {
  for (const elemento of document.querySelectorAll("[data-entrada] button, [data-entrada] select, [data-salida]")) {
    elemento.disabled = Boolean(control.actual) || cargando;
  }
  $("[data-reintento]").hidden = !control.actual || control.enCurso;
  $("[data-reintentar]").disabled = control.enCurso || cargando;
  $("[data-descartar]").disabled = control.enCurso;
}

function dibujarVisitas(visitas) {
  $("[data-visitas]").replaceChildren();
  $("[data-vacio]").hidden = visitas.length !== 0;
  for (const visita of visitas) {
    const tarjeta = document.createElement("li");
    tarjeta.className = "tarjeta";
    const titulo = document.createElement("h3");
    titulo.textContent = visita.nombre;
    const detalle = document.createElement("p");
    detalle.textContent = `Cédula ${formatearCedula(visita.cedula)} · Entrada ${formatearFechaHora(visita.entrada)} · ${Math.floor(visita.duracion / 60)} min`;
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
    tarjeta.append(titulo, detalle, boton);
    $("[data-visitas]").append(tarjeta);
  }
}

async function actualizar() {
  if (!autorizada || cargando || control.enCurso) return;
  cargando = true;
  actualizarBotones();
  try {
    const [ocupacion, { visitas }, { socios }] = await Promise.all([
      llamarApi("/api/ocupacion"), llamarApi("/api/visitas?abiertas=1"), llamarApi("/api/visitas/socios"),
    ]);
    sedeId = ocupacion.sede_id;
    $("[data-ocupacion]").textContent = `${ocupacion.ocupacion_registrada} de ${ocupacion.aforo_maximo}`;
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
    await llamarApi(operacion.ruta, { metodo: "POST", cuerpo: operacion.cuerpo, clave: operacion.clave });
    control.finalizar();
    $("[data-estado]").textContent = operacion.ruta === "/api/entradas" ? "Entrada registrada." : "Salida registrada.";
    await actualizar();
    $("#socio").focus();
  } catch (error) {
    control.finalizar(error);
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = control.actual ? "No se confirmó la operación. Podés reintentar o descartar el reintento." : "La operación fue rechazada.";
  } finally {
    actualizarBotones();
  }
}

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
    if (await actualizar()) $("[data-estado]").textContent = "Recepción lista.";
  } catch (error) { $("[data-error]").textContent = error.message; }
}
iniciar();
