import { llamarApi } from "./api.js";
import { cerrarSesion } from "./operaciones.js";

// Lo común a las pantallas del entrenador y de administración.

export function crear(etiqueta, propiedades = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(propiedades)) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (clave.startsWith("data-") || clave.startsWith("aria-") || clave === "role") nodo.setAttribute(clave, valor);
    else nodo[clave] = valor;
  }
  nodo.append(...hijos.flat().filter((hijo) => hijo !== null && hijo !== undefined && hijo !== false));
  return nodo;
}

/** Devuelve la persona con sesión, o manda a la pantalla inicial si su rol no entra acá. */
export async function exigirRol(roles) {
  const { usuario } = await llamarApi("/api/sesion");
  if (usuario && roles.includes(usuario.rol)) return usuario;
  location.replace("/");
  return null;
}

export function prepararBarra(usuario) {
  const demo = document.querySelector("[data-demo]");
  if (demo) demo.hidden = !usuario.es_demo;
  // Administración no tiene bandeja: la sección queda solo para el entrenador.
  for (const enlace of document.querySelectorAll("[data-solo-entrenador]")) enlace.hidden = usuario.rol !== "entrenador";
  for (const enlace of document.querySelectorAll("[data-solo-administracion]")) enlace.hidden = usuario.rol !== "administracion";
  document.querySelector("[data-cerrar]").addEventListener("click", async (evento) => {
    evento.currentTarget.disabled = true;
    try {
      await cerrarSesion(llamarApi);
    } finally {
      location.replace("/");
    }
  });
}
