import { llamarApi } from "@comun/api.js";
import { crear } from "@comun/personal.js";
import { formatearGuaranies } from "@comun/formatos.js";

export function prepararTiposMembresia() {
  const seccion = document.querySelector("#tipos-membresia");
  const formulario = seccion.querySelector("form");
  const estado = seccion.querySelector("[data-tipos-estado]");
  const error = seccion.querySelector("[data-tipos-error]");
  const lista = seccion.querySelector("[data-tipos-lista]");
  let editando = null;
  let pendiente;
  let ocupado = false;

  function nuevo() {
    formulario.reset();
    editando = null;
    formulario.querySelector("[type=submit]").textContent = "Crear tipo de membresía";
  }

  async function cargar() {
    estado.textContent = "Cargando tipos de membresía…";
    error.textContent = "";
    try {
      const { tipos } = await llamarApi("/api/tipos-membresia");
      lista.replaceChildren(...tipos.map((tipo) => crear("li", {},
        crear("p", {}, `${tipo.nombre} · ${tipo.duracion_dias} días · ${formatearGuaranies(tipo.precio)}${tipo.archivado ? " · Archivado" : ""}`),
        crear("button", { type: "button", onclick: () => {
          if (ocupado) return;
          editando = tipo.id;
          for (const campo of ["nombre", "duracion_dias", "precio"]) formulario.elements[campo].value = tipo[campo];
          formulario.querySelector("[type=submit]").textContent = "Guardar tipo de membresía";
          formulario.elements.nombre.focus();
        } }, "Editar"), " ",
        !tipo.archivado && crear("button", { type: "button", onclick: () => guardar(`/api/tipos-membresia/${tipo.id}/archivar`, "POST", undefined) }, "Archivar"))));
      estado.textContent = tipos.length ? "" : "No hay tipos de membresía. Creá el primero para registrar pagos.";
    } catch (fallo) {
      estado.textContent = "";
      error.textContent = fallo.message;
    }
  }

  async function guardar(ruta, metodo, cuerpo) {
    if (ocupado) return;
    ocupado = true;
    formulario.querySelector("fieldset").disabled = true;
    estado.textContent = "Guardando tipo de membresía…";
    error.textContent = "";
    const huella = JSON.stringify([ruta, metodo, cuerpo]);
    if (pendiente?.huella !== huella) pendiente = { huella, clave: crypto.randomUUID() };
    try {
      await llamarApi(ruta, { metodo, cuerpo, clave: pendiente.clave });
      pendiente = null;
      nuevo();
      await cargar();
    } catch (fallo) {
      estado.textContent = "";
      error.textContent = fallo.message;
    } finally {
      ocupado = false;
      formulario.querySelector("fieldset").disabled = false;
    }
  }

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const cuerpo = Object.fromEntries(new FormData(formulario));
    cuerpo.duracion_dias = Number(cuerpo.duracion_dias);
    cuerpo.precio = Number(cuerpo.precio);
    guardar(editando ? `/api/tipos-membresia/${editando}` : "/api/tipos-membresia", editando ? "PUT" : "POST", cuerpo);
  });
  seccion.querySelector("[data-tipo-nuevo]").addEventListener("click", nuevo);
  seccion.querySelector("[data-tipos-recargar]").addEventListener("click", cargar);
  return cargar();
}
