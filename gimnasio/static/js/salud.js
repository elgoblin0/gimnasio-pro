import { llamarApi } from "./comun/api.js";
import { crear } from "./comun/personal.js";
import { nuevoId } from "./comun/ids.js";
import { formatearFechaHora } from "./comun/formatos.js";
import { ZONAS_CUERPO } from "./comun/zonas.js";

const lecturas = new WeakMap();
const finalidad = "Usamos las condiciones, restricciones y dolores para adaptar el entrenamiento y aplicar los frenos de seguridad.";

export async function montarSalud(contenedor, socio = null, alGuardar = () => {}) {
  const lectura = {};
  lecturas.set(contenedor, lectura);
  const ruta = socio ? `/api/socios/${encodeURIComponent(socio)}/salud` : "/api/yo/salud";
  contenedor.replaceChildren(crear("h2", {}, "Salud"), crear("p", { role: "status" }, "Cargando salud…"));
  try {
    const salud = await llamarApi(ruta);
    const ejercicios = socio ? (await llamarApi("/api/ejercicios")).ejercicios : [];
    if (lecturas.get(contenedor) !== lectura) return;
    contenedor.replaceChildren(crear("h2", {}, "Salud"));
    const estado = crear("p", { role: "status" });
    contenedor.append(estado);

    function formulario(titulo, destino, campos, datos) {
      const boton = crear("button", { type: "submit" }, titulo);
      const forma = crear("form", {}, crear("p", {}, finalidad), campos, boton);
      let pendiente;
      forma.addEventListener("input", () => { pendiente = null; });
      forma.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        boton.disabled = true;
        estado.textContent = "Guardando…";
        pendiente ??= { clave: crypto.randomUUID(), cuerpo: datos(new FormData(forma)) };
        try {
          await llamarApi(destino, { metodo: "POST", ...pendiente });
          if (lecturas.get(contenedor) !== lectura) return;
          await montarSalud(contenedor, socio, alGuardar);
          alGuardar();
        } catch (error) {
          estado.textContent = error.message;
          boton.disabled = false;
        }
      });
      return forma;
    }
    const texto = (nombre, etiqueta, requerido = true) => crear("label", {}, etiqueta,
      crear("textarea", { name: nombre, maxLength: 1000, required: requerido, rows: 3 }));
    const fecha = (valor) => formatearFechaHora(valor);
    contenedor.append(crear("h3", {}, "Condiciones de salud"));
    if (!salud.condiciones.length) contenedor.append(crear("p", {}, "Sin condiciones de salud declaradas."));
    for (const condicion of salud.condiciones) {
      const fila = crear("article", {}, crear("p", {}, condicion.descripcion),
        crear("p", {}, `${fecha(condicion.registrada_en)} · ${condicion.revision_id ? "Revisada" : "Sin revisar"}`));
      if (condicion.nota) fila.append(crear("p", {}, condicion.nota));
      if (!socio) {
        const reemplazar = formulario("Reemplazar condición", `${ruta}/condiciones`,
          texto("descripcion", "Nueva descripción"), (campos) => ({
            id: nuevoId(), descripcion: campos.get("descripcion"), reemplaza_a: condicion.id,
          }));
        fila.append(crear("details", {}, crear("summary", {}, "Reemplazar condición"), reemplazar));
      } else if (!condicion.revision_id) {
        fila.append(formulario("Marcar condición revisada", `${ruta}/condiciones/${condicion.id}/revisar`,
          texto("nota", "Nota de revisión (opcional)", false), (campos) => ({ nota: campos.get("nota") || null })));
      }
      contenedor.append(fila);
    }
    if (!socio) contenedor.append(formulario("Declarar condición", `${ruta}/condiciones`,
      texto("descripcion", "Condición de salud"), (campos) => ({ id: nuevoId(), descripcion: campos.get("descripcion") })));
    contenedor.append(crear("h3", {}, "Restricciones vigentes"));
    if (!salud.restricciones.length) contenedor.append(crear("p", {}, "Sin restricciones de salud vigentes."));
    for (const restriccion of salud.restricciones) {
      const objetivo = ejercicios.find((e) => e.id === restriccion.ejercicio_id)?.nombre
        ?? ZONAS_CUERPO.find((z) => z.id === restriccion.zona)?.nombre
        ?? restriccion.patron_movimiento ?? "Ejercicio";
      const fila = crear("article", {}, crear("p", {}, `${objetivo}: ${restriccion.descripcion}`));
      if (socio) fila.append(formulario("Levantar restricción", `${ruta}/restricciones/${restriccion.id}/levantar`, [], () => ({})));
      contenedor.append(fila);
    }
    if (socio) {
      const tipo = crear("select", { name: "tipo", "aria-label": "Objetivo" },
        ...[["ejercicio_id", "Ejercicio"], ["patron_movimiento", "Patrón de movimiento"], ["zona", "Zona del cuerpo"]]
          .map(([value, nombre]) => crear("option", { value }, nombre)));
      const busqueda = crear("input", { type: "search", placeholder: "Buscar objetivo" });
      const objetivo = crear("select", { name: "objetivo", required: true, size: 5, "aria-label": "Resultado" });
      const actualizar = () => {
        const opciones = tipo.value === "ejercicio_id" ? ejercicios.map((e) => [e.id, e.nombre])
          : tipo.value === "zona" ? ZONAS_CUERPO.map((z) => [z.id, z.nombre])
            : [...new Set(ejercicios.map((e) => e.patron_movimiento))].filter(Boolean).map((p) => [p, p]);
        objetivo.replaceChildren(...opciones.filter(([, nombre]) => nombre.toLocaleLowerCase("es").includes(busqueda.value.toLocaleLowerCase("es")))
          .map(([value, nombre]) => crear("option", { value }, nombre)));
      };
      tipo.addEventListener("change", actualizar);
      busqueda.addEventListener("input", actualizar);
      actualizar();
      const condicion = crear("select", { name: "condicion_id", "aria-label": "Condición que se revisa" }, crear("option", { value: "" }, "Sin condición asociada"),
        ...salud.condiciones.filter((c) => !c.revision_id).map((c) => crear("option", { value: c.id }, c.descripcion)));
      contenedor.append(crear("h3", {}, "Registrar restricción"), formulario("Registrar restricción", `${ruta}/restricciones`,
        [crear("label", {}, "Objetivo", tipo), crear("label", {}, "Buscar ejercicio, patrón o zona", busqueda),
          crear("label", {}, "Resultado", objetivo), texto("descripcion", "Descripción de la restricción"),
          crear("label", {}, "Condición que se revisa", condicion)], (campos) => ({
          id: nuevoId(), [campos.get("tipo")]: campos.get("objetivo"), descripcion: campos.get("descripcion"),
          ...(campos.get("condicion_id") ? { condicion_id: campos.get("condicion_id") } : {}),
        })));
    }
    contenedor.append(crear("h3", {}, "Dolores reportados"));
    contenedor.append(salud.dolores.length ? crear("ul", {}, ...salud.dolores.map((d) => crear("li", {},
      `${ZONAS_CUERPO.find((z) => z.id === d.zona)?.nombre ?? d.zona} · ${fecha(d.registrado_en)}`)))
      : crear("p", {}, "Sin dolores reportados."));
  } catch (error) {
    if (lecturas.get(contenedor) !== lectura) return;
    const reintentar = crear("button", { type: "button" }, "Reintentar salud");
    reintentar.addEventListener("click", () => montarSalud(contenedor, socio, alGuardar));
    contenedor.replaceChildren(crear("h2", {}, "Salud"), crear("p", { role: "alert" }, error.message), reintentar);
  }
}
