import { llamarApi } from "@comun/api.js";

const estado = document.querySelector("[data-estado]");

try {
  const datos = await llamarApi("/api/estado");
  estado.textContent = datos.modo_demo ? "Modo demo: datos ficticios que se reinician cada día." : "Servicio en línea.";
} catch {
  estado.textContent = "No se pudo conectar con el servidor.";
}
