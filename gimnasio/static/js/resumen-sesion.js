import { llamarApi } from "@comun/api.js";
import { formatearCarga } from "@comun/formatos.js";
import { textoMotivoSustitucion } from "@comun/sustituciones.js";
import { crearResumenZonas, ZONAS_CUERPO } from "@comun/zonas.js";

const $ = (selector) => document.querySelector(selector);
function lista(selector, textos, vacio) {
  $(selector).replaceChildren(...(textos.length ? textos : [vacio]).map((texto) => {
    const fila = document.createElement("li");
    fila.textContent = texto;
    return fila;
  }));
}
async function actualizar() {
  $("[data-actualizar]").disabled = true;
  $("[data-resumen]").hidden = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando resumen…";
  try {
    const sesion = new URL(location.href).searchParams.get("sesion");
    if (!sesion) throw new Error("Elegí una sesión realizada desde tu entrenamiento.");
    const [datos, estado] = await Promise.all([
      llamarApi(`/api/entrenamiento/sesiones/${encodeURIComponent(sesion)}/resumen`), llamarApi("/api/estado"),
    ]);
    $("[data-demo]").hidden = !estado.modo_demo;
    const zonas = $("[data-zonas-resumen]");
    zonas.replaceChildren();
    crearResumenZonas(zonas, datos.zonas_trabajadas, datos.zonas_con_dolor);
    lista("[data-zonas-texto]", ZONAS_CUERPO.filter((z) => datos.zonas_trabajadas.includes(z.id) || datos.zonas_con_dolor.includes(z.id)).map((z) =>
      `${z.nombre}: ${[datos.zonas_trabajadas.includes(z.id) ? "trabajada" : "", datos.zonas_con_dolor.includes(z.id) ? "con dolor" : ""].filter(Boolean).join(" y ")}`), "Sin zonas trabajadas ni dolor reportado.");
    lista("[data-records]", datos.records.map((r) => `${r.ejercicio_hecho_nombre}: ${r.medida === "carga_maxima" ? formatearCarga(r.marca) : `${r.marca} repeticiones a ${formatearCarga(r.carga)}`}`), "Sin récords batidos en esta sesión.");
    lista("[data-sustituciones]", datos.sustituciones.map((s) => `${s.ejercicio_planificado_nombre} → ${s.ejercicio_hecho_nombre}: ${textoMotivoSustitucion(s.motivo)}`), "Sin sustituciones en esta sesión.");
    lista("[data-pendientes]", datos.pendientes.map((p) => `${datos.ejercicios.find((e) => e.id === p.ejercicio_id)?.nombre}: series ${p.series.join(", ")}`), "Sin series pendientes.");
    $("[data-resumen]").hidden = false;
    $("[data-estado]").textContent = "Resumen actualizado.";
  } catch (error) {
    $("[data-error]").textContent = error.message;
    $("[data-estado]").textContent = "No se pudo cargar el resumen. Podés actualizar para reintentar.";
  } finally { $("[data-actualizar]").disabled = false; }
}
$("[data-actualizar]").addEventListener("click", actualizar);
actualizar();
