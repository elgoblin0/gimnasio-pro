import { llamarApi } from "@comun/api.js";
import { crear } from "@comun/personal.js";
import { textoSemana, textosCambios, textosCumplido, textosPendientes } from "./resumen-semanal-textos.js";

// El socio lo ve en su inicio y el entrenador en la vista del socio: misma lectura, distinta ruta.
const lecturas = new WeakMap();

function lista(textos, vacio) {
  return textos.length
    ? crear("ul", {}, textos.map((texto) => crear("li", {}, texto)))
    : crear("p", { className: "nota-suave" }, vacio);
}

function dibujar(contenedor, ruta, resumen) {
  const { semana } = resumen;
  const pendientes = textosPendientes(resumen.pendientes);
  const navegar = (lunes, texto, rotulo) => crear("button", {
    type: "button",
    disabled: !lunes,
    "aria-label": rotulo,
    onclick: () => montarResumenSemanal(contenedor, ruta, lunes),
  }, texto);
  contenedor.replaceChildren(
    crear("div", { className: "resumen-semanal-navegacion" },
      navegar(semana.anterior, "←", "Semana anterior"),
      crear("strong", { "data-resumen-semana": semana.lunes }, textoSemana(semana)),
      navegar(semana.siguiente, "→", "Semana siguiente")),
    ...(resumen.sin_actividad
      ? [crear("p", { className: "nota-suave" }, "No hubo sesiones ni visitas en esta semana.")]
      : [
        crear("h4", {}, "Cumplido"),
        lista(textosCumplido(resumen.cumplido), ""),
        crear("h4", {}, "Cambios"),
        lista(textosCambios(resumen.cambios), "Sin ajustes ni frenos en la semana."),
      ]),
    crear("h4", {}, "Pendientes"),
    lista(pendientes, "Nada pendiente."),
  );
}

export async function montarResumenSemanal(contenedor, ruta, semana = null) {
  const lectura = (lecturas.get(contenedor) ?? 0) + 1;
  lecturas.set(contenedor, lectura);
  contenedor.setAttribute("aria-busy", "true");
  contenedor.replaceChildren(crear("p", { className: "nota-suave", role: "status" }, "Cargando el resumen semanal…"));
  try {
    const resumen = await llamarApi(semana ? `${ruta}?semana=${encodeURIComponent(semana)}` : ruta);
    if (lecturas.get(contenedor) === lectura) dibujar(contenedor, ruta, resumen);
  } catch (error) {
    if (lecturas.get(contenedor) !== lectura) return;
    contenedor.replaceChildren(
      crear("p", { role: "alert" }, error.message),
      crear("button", { type: "button", onclick: () => montarResumenSemanal(contenedor, ruta, semana) }, "Reintentar"),
    );
  } finally {
    if (lecturas.get(contenedor) === lectura) contenedor.removeAttribute("aria-busy");
  }
}
