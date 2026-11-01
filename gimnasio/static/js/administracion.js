import { llamarApi } from "@comun/api.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { formatearFechaHora } from "@comun/formatos.js";
import { registrarPwa } from "@comun/pwa.js";
import { prepararTiposMembresia } from "./tipos-membresia.js";
import { prepararUsuarios } from "./usuarios.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
const dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
let pendiente;

function intervalo(dia, apertura = "06:00", cierre = "22:00") {
  const fila = crear("div", { "data-intervalo": "" },
    crear("label", {}, "Desde ", crear("input", { type: "time", value: apertura, required: true, "aria-label": `Apertura del ${dia}` })),
    " ", crear("label", {}, "Hasta ", crear("input", { type: "time", value: cierre, required: true, "aria-label": `Cierre del ${dia}` })),
    " ", crear("button", { type: "button", className: "boton-borde", onclick: () => fila.remove() }, "Quitar intervalo"));
  return fila;
}

function mostrar(datos) {
  $("[data-ocupacion]").textContent = `Ocupación registrada: ${datos.ocupacion_registrada} · Aforo máximo: ${datos.aforo_maximo}`;
  $("#aforo").value = datos.aforo_maximo;
  $("[data-horario]").replaceChildren(...dias.map((dia, indice) => {
    const numero = String(indice + 1);
    const intervalos = crear("div", {}, ...(datos.horario[numero] ?? []).map(([desde, hasta]) => intervalo(dia, desde, hasta)));
    const abierto = crear("input", { type: "checkbox", checked: Boolean(datos.horario[numero]?.length), onchange: () => {
      intervalos.hidden = !abierto.checked;
      agregar.hidden = !abierto.checked;
      if (abierto.checked && !intervalos.children.length) intervalos.append(intervalo(dia));
      for (const entrada of intervalos.querySelectorAll("input")) entrada.disabled = !abierto.checked;
    } });
    const agregar = crear("button", { type: "button", className: "boton-borde", onclick: () => intervalos.append(intervalo(dia)) }, "Agregar intervalo");
    intervalos.hidden = agregar.hidden = !abierto.checked;
    return crear("fieldset", { "data-dia": numero }, crear("legend", {}, dia), crear("label", {}, abierto, " Abierto"), intervalos, agregar);
  }));
  $("[data-sin-cambios]").hidden = datos.historial.length > 0;
  $("[data-historial]").replaceChildren(...datos.historial.map((cambio) => crear("li", {},
    crear("p", {}, `${formatearFechaHora(cambio.registrado_en)} · ${cambio.autor} · Aforo máximo: ${cambio.aforo_maximo}`),
    crear("p", {}, cambio.motivo),
    crear("ul", {}, ...dias.map((dia, indice) => crear("li", {}, `${dia}: ${(cambio.horario[String(indice + 1)] ?? []).map((par) => par.join("–")).join(", ") || "Cerrado"}`))))));
  $("[data-contenido]").hidden = false;
}

async function cargar() {
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando sede…";
  $("[data-reintentar]").hidden = true;
  try {
    mostrar(await llamarApi("/api/administracion/sede"));
    $("[data-estado]").textContent = "";
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
    $("[data-reintentar]").hidden = false;
  }
}

async function guardar(evento) {
  evento.preventDefault();
  const boton = evento.target.querySelector("[type=submit]");
  boton.disabled = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Guardando cambios…";
  const horario = {};
  for (const campo of document.querySelectorAll("[data-dia]")) {
    if (campo.querySelector("[type=checkbox]").checked) horario[campo.dataset.dia] = [...campo.querySelectorAll("[data-intervalo]")].map((fila) => [...fila.querySelectorAll("input")].map((input) => input.value));
  }
  const cuerpo = { aforo_maximo: Number($("#aforo").value), horario, motivo: $("#motivo").value };
  // Un reintento del mismo cuerpo conserva la clave incluso si se perdió la respuesta.
  const huella = JSON.stringify(cuerpo);
  if (pendiente?.huella !== huella) pendiente = { huella, clave: crypto.randomUUID() };
  try {
    mostrar(await llamarApi("/api/administracion/sede", { metodo: "PUT", cuerpo, clave: pendiente.clave }));
    pendiente = null;
    $("#motivo").value = "";
    $("[data-estado]").textContent = "Cambios guardados.";
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
  } finally {
    boton.disabled = false;
  }
}

async function iniciar() {
  const usuario = await exigirRol(["administracion"]);
  if (!usuario) return;
  prepararBarra(usuario);
  $("[data-formulario]").addEventListener("submit", guardar);
  $("[data-reintentar]").addEventListener("click", cargar);
  await Promise.all([cargar(), prepararTiposMembresia(), prepararUsuarios()]);
}
iniciar().catch((error) => { $("[data-estado]").textContent = ""; $("[data-error]").textContent = error.message; });
