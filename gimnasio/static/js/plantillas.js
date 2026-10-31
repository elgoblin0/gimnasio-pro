import { llamarApi } from "@comun/api.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);

async function cargar() {
  $("[data-estado]").textContent = "Cargando plantillas…";
  $("[data-error]").textContent = "";
  $("[data-reintentar]").hidden = true;
  try {
    const { plantillas } = await llamarApi("/api/programas/plantillas");
    $("[data-plantillas]").replaceChildren(...plantillas.map((plantilla) => {
      let clave = null;
      const archivar = crear("button", { type: "button", className: "boton-borde", onclick: async () => {
        archivar.disabled = true;
        $("[data-error]").textContent = "";
        $("[data-estado]").textContent = "Archivando plantilla…";
        clave ??= crypto.randomUUID();
        try {
          await llamarApi(`/api/programas/plantillas/${plantilla.id}/archivar`, { metodo: "POST", cuerpo: {}, clave });
          await cargar();
        } catch (error) {
          if (error.estadoHttp !== 0 && error.estadoHttp < 500) clave = null;
          $("[data-estado]").textContent = "";
          $("[data-error]").textContent = error.message;
          archivar.disabled = false;
        }
      } }, "Archivar");
      return crear("li", {}, crear("h2", {}, plantilla.nombre),
        crear("p", {}, plantilla.archivada ? "Archivada" : "Activa"),
        crear("p", {}, plantilla.descripcion),
        crear("p", {}, `${plantilla.sesiones.length} sesiones`),
        crear("a", { href: `/editor-programa.html?plantilla=${plantilla.id}`, className: "boton-borde" }, "Editar"),
        plantilla.archivada ? null : archivar);
    }));
    $("[data-estado]").textContent = plantillas.length ? "" : "No hay plantillas.";
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
    $("[data-reintentar]").hidden = false;
  }
}

async function iniciar() {
  const usuario = await exigirRol(["administracion"]);
  if (!usuario) return;
  prepararBarra(usuario);
  $("[data-reintentar]").addEventListener("click", cargar);
  await cargar();
}
iniciar().catch((error) => { $("[data-estado]").textContent = ""; $("[data-error]").textContent = error.message; });
