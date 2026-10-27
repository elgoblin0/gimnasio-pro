import { llamarApi } from "@comun/api.js";
import { formatearCarga, formatearFecha } from "@comun/formatos.js";
import { cerrarSesion } from "@comun/operaciones.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
let autorizada = false;
let cargando = false;
const numero = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });

function describirObjetivos(objetivos) {
  const partes = [`${objetivos.series} ${objetivos.series === 1 ? "serie" : "series"}`];
  if (objetivos.repeticiones !== null) partes.push(`${objetivos.repeticiones} repeticiones`);
  if (objetivos.carga !== null) partes.push(formatearCarga(objetivos.carga));
  if (objetivos.duracion !== null) partes.push(`${objetivos.duracion} s`);
  if (objetivos.distancia !== null) partes.push(`${numero.format(Number(objetivos.distancia))} m`);
  return partes.join(" · ");
}

function dibujar(propuesta) {
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
    $("[data-ejercicios]").append(tarjeta);
  }
  $("[data-contenido]").hidden = false;
}

async function actualizar() {
  if (!autorizada || cargando) return;
  cargando = true;
  $("[data-actualizar]").disabled = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando tu propuesta…";
  try {
    dibujar(await llamarApi("/api/entrenamiento/propuesta"));
    $("[data-estado]").textContent = "Propuesta actualizada.";
  } catch (error) {
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = "No se pudo cargar la propuesta. Podés actualizar para reintentar.";
    $("[data-contenido]").hidden = true;
  } finally {
    cargando = false;
    $("[data-actualizar]").disabled = false;
  }
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
$("[data-cerrar]").addEventListener("click", async () => {
  try { await cerrarSesion(llamarApi); location.assign("/"); }
  catch (error) { $("[data-error]").textContent = error.message; }
});
iniciar();
