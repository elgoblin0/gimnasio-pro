import { llamarApi } from "@comun/api.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const formulario = document.querySelector("form");
const estado = document.querySelector("[data-resultado]");
let pendiente;
formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const boton = formulario.querySelector("button");
  boton.disabled = true;
  pendiente ??= { cuerpo: Object.fromEntries(new FormData(formulario)), clave: crypto.randomUUID() };
  estado.textContent = "Cambiando clave…";
  try {
    await llamarApi("/api/sesion/clave", { metodo: "POST", ...pendiente });
    pendiente = null;
    formulario.reset();
    location.replace("/");
  } catch (error) {
    if (error.estadoHttp > 0 && error.estadoHttp < 500 && error.codigo !== "solicitud_en_curso") pendiente = null;
    estado.textContent = error.message;
    boton.textContent = pendiente ? "Reintentar el mismo cambio" : "Cambiar clave";
  } finally {
    boton.disabled = false;
    for (const entrada of formulario.querySelectorAll("input")) entrada.disabled = Boolean(pendiente);
  }
});
document.querySelector("[data-salir]").addEventListener("click", async () => {
  try {
    await llamarApi("/api/sesion", { metodo: "DELETE" });
    location.replace("/");
  } catch (error) { estado.textContent = error.message; }
});
