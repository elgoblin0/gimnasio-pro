import { llamarApi } from "./comun/api.js";
import { crear } from "./comun/personal.js";
import { formatearFechaHora } from "./comun/formatos.js";

export async function montarConsultasFicha(contenedor) {
  contenedor.hidden = false;
  const estado = crear("p", { role: "status" });
  const lista = crear("div");
  const anterior = crear("button", { type: "button" }, "Anterior");
  const siguiente = crear("button", { type: "button" }, "Siguiente");
  const reintentar = crear("button", { type: "button", hidden: true }, "Reintentar");
  const descarga = crear("button", { type: "button" }, "Descargar mis datos");
  const estadoDescarga = crear("p", { role: "status" });
  contenedor.replaceChildren(crear("h2", {}, "Consultas de ficha"), estado, lista, anterior, siguiente, reintentar, descarga, estadoDescarga);
  let pagina = 1;
  let hayMas = false;
  async function cargar(destino = pagina) {
    anterior.disabled = siguiente.disabled = reintentar.disabled = true;
    estado.textContent = "Cargando consultas de ficha…";
    try {
      const datos = await llamarApi(`/api/yo/salud/consultas?pagina=${destino}`);
      pagina = datos.pagina;
      hayMas = datos.hay_mas;
      lista.replaceChildren(...datos.consultas.map((consulta) => crear("p", {},
        `${consulta.nombre} ${consulta.apellido} · ${consulta.rol} · ${formatearFechaHora(consulta.registrada_en)}`)));
      estado.textContent = datos.consultas.length ? `Página ${pagina}` : "Todavía no hay consultas de tu ficha de salud.";
      reintentar.hidden = true;
    } catch (error) {
      estado.textContent = error.message;
      reintentar.hidden = false;
    } finally {
      anterior.disabled = pagina === 1;
      siguiente.disabled = !hayMas;
      reintentar.disabled = false;
    }
  }
  anterior.addEventListener("click", () => cargar(pagina - 1));
  siguiente.addEventListener("click", () => cargar(pagina + 1));
  reintentar.addEventListener("click", () => cargar());
  descarga.addEventListener("click", async () => {
    descarga.disabled = true;
    estadoDescarga.textContent = "Preparando descarga…";
    try {
      const datos = await llamarApi("/api/yo/datos");
      const direccion = URL.createObjectURL(new Blob([JSON.stringify(datos, null, 2)], { type: "application/json" }));
      const enlace = crear("a", { href: direccion, download: "mis-datos.json" });
      contenedor.append(enlace);
      enlace.click();
      enlace.remove();
      setTimeout(() => URL.revokeObjectURL(direccion), 1000);
      estadoDescarga.textContent = "Datos descargados.";
    } catch (error) {
      estadoDescarga.textContent = error.message;
    } finally { descarga.disabled = false; }
  });
  await cargar();
}
