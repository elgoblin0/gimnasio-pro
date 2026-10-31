import { llamarApi } from "@comun/api.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { formatearCedula, formatearGuaranies, formatearFecha } from "@comun/formatos.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
let socios = [];
let tipos = [];
let pendiente;

function buscar() {
  const texto = $("#buscar").value.trim().toLocaleLowerCase("es");
  const cedula = texto.replace(/[. ]/g, "");
  const anterior = $("#socio").value;
  const encontrados = socios.filter((socio) => socio.nombre.toLocaleLowerCase("es").includes(texto) || (cedula && socio.cedula.includes(cedula)));
  $("#socio").replaceChildren(crear("option", { value: "" }, "Elegí un socio"), ...encontrados.map((socio) => crear("option", { value: socio.id }, `${socio.nombre} · ${formatearCedula(socio.cedula)}`)));
  if (encontrados.some((socio) => socio.id === anterior)) $("#socio").value = anterior;
  $("[data-socios-estado]").textContent = encontrados.length ? `${encontrados.length} socios encontrados.` : "No hay socios para esa búsqueda.";
}

async function cargar() {
  $("[data-pago]").hidden = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando socios y tipos de membresía…";
  try {
    const [personas, catalogo] = await Promise.all([llamarApi("/api/pagos/socios"), llamarApi("/api/tipos-membresia")]);
    socios = personas.socios;
    tipos = catalogo.tipos.filter((tipo) => !tipo.archivado);
    buscar();
    $("#tipo").replaceChildren(crear("option", { value: "" }, "Elegí un tipo de membresía"), ...tipos.map((tipo) => crear("option", { value: tipo.id }, `${tipo.nombre} · ${tipo.duracion_dias} días · ${formatearGuaranies(tipo.precio)}`)));
    $("[data-precio]").textContent = "";
    $("[data-pago]").hidden = !socios.length || !tipos.length;
    $("[data-estado]").textContent = !tipos.length ? "No hay tipos de membresía disponibles. Administración debe configurar uno." : !socios.length ? "No hay socios activos." : "";
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
  }
}

async function registrar(evento) {
  evento.preventDefault();
  const formulario = evento.target;
  const cuerpo = Object.fromEntries(new FormData(formulario));
  if (cuerpo.monto === "") delete cuerpo.monto;
  else cuerpo.monto = Number(cuerpo.monto);
  const huella = JSON.stringify(cuerpo);
  // Una respuesta perdida conserva la clave para reintentar sin otro pago.
  if (pendiente?.huella !== huella) pendiente = { huella, clave: crypto.randomUUID() };
  formulario.querySelector("fieldset").disabled = true;
  $("[data-recargar]").disabled = true;
  $("[data-estado]").textContent = "Registrando pago y renovando membresía…";
  $("[data-error]").textContent = "";
  $("[data-resultado]").textContent = "";
  try {
    const pago = await llamarApi("/api/pagos", { metodo: "POST", cuerpo, clave: pendiente.clave });
    pendiente = null;
    formulario.reset();
    buscar();
    $("[data-precio]").textContent = "";
    $("[data-resultado]").textContent = `Pago registrado: ${formatearGuaranies(pago.monto)}. Membresía del ${formatearFecha(pago.membresia.desde)} al ${formatearFecha(pago.membresia.hasta)}.`;
  } catch (error) {
    $("[data-error]").textContent = error.message;
  } finally {
    $("[data-estado]").textContent = "";
    formulario.querySelector("fieldset").disabled = false;
    $("[data-recargar]").disabled = false;
  }
}

async function iniciar() {
  const usuario = await exigirRol(["recepcion", "administracion"]);
  if (!usuario) return;
  prepararBarra(usuario);
  $("[data-solo-recepcion]").hidden = usuario.rol !== "recepcion";
  $("#buscar").addEventListener("input", buscar);
  $("#tipo").addEventListener("change", () => {
    const tipo = tipos.find((tipo) => tipo.id === $("#tipo").value);
    $("[data-precio]").textContent = tipo ? `Precio: ${formatearGuaranies(tipo.precio)} · Duración: ${tipo.duracion_dias} días` : "";
  });
  $("[data-pago]").addEventListener("submit", registrar);
  $("[data-recargar]").addEventListener("click", cargar);
  await cargar();
}
iniciar().catch((error) => { $("[data-estado]").textContent = ""; $("[data-error]").textContent = error.message; });
