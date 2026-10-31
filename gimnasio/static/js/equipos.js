import { llamarApi } from "@comun/api.js";
import { formatearFechaHora } from "@comun/formatos.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { registrarPwa } from "@comun/pwa.js";
import {
  candidatosDeAlternativa, ejerciciosDelEquipo, mensajeLegible, moverEnLista, nombreDeEquipo, sinAlternativaDisponible,
} from "./equipos-datos.js";

registrarPwa();

const $ = (selector) => document.querySelector(selector);
let equipos = [];
let catalogo = [];
let porId = new Map();
// Equipo cuyo paso a fuera de servicio se está confirmando, con su motivo opcional.
let confirmando = null;
const erroresEquipo = new Map();
const erroresEjercicio = new Map();
// Una clave por intento: si se corta la red, reintentar con el mismo cuerpo no duplica el cambio.
const pendientes = new Map();

function indexar() {
  const estados = new Map(equipos.map((equipo) => [equipo.nombre, equipo.estado]));
  catalogo = catalogo.map((ejercicio) => ({ ...ejercicio, estado_equipo: estados.get(ejercicio.equipo) ?? "disponible" }));
  porId = new Map(catalogo.map((ejercicio) => [ejercicio.id, ejercicio]));
}

function enviar(ruta, cuerpo) {
  const huella = JSON.stringify(cuerpo);
  const previo = pendientes.get(ruta);
  const clave = previo?.huella === huella ? previo.clave : crypto.randomUUID();
  pendientes.set(ruta, { huella, clave });
  return llamarApi(ruta, { metodo: "POST", cuerpo, clave }).then(
    (respuesta) => { pendientes.delete(ruta); return respuesta; },
    (error) => { if (error.estadoHttp !== 0 && error.estadoHttp < 500) pendientes.delete(ruta); throw error; },
  );
}

function filaDeEquipo(equipo) {
  const fuera = equipo.estado === "fuera_de_servicio";
  const usos = ejerciciosDelEquipo(equipo, catalogo);
  const idMotivo = `motivo-${equipo.id}`;
  const pidiendoMotivo = confirmando === equipo.id;
  const cambio = equipo.ultimo_cambio ? `Último cambio: ${formatearFechaHora(equipo.ultimo_cambio)}` : "Sin cambios registrados";
  return crear("li", { className: "fila-equipo", "data-equipo": equipo.nombre, "data-estado-equipo": equipo.estado },
    crear("div", { className: "equipo-datos" },
      crear("p", { className: "equipo-nombre" }, crear("span", {}, nombreDeEquipo(equipo.nombre)),
        crear("span", { className: "sello-estado" }, fuera ? "Fuera de servicio" : "Disponible")),
      crear("p", { className: "nota-suave" }, [cambio, fuera && equipo.motivo ? `Motivo: ${equipo.motivo}` : null].filter(Boolean).join(" · ")),
      crear("p", { className: "nota-suave" }, usos.length ? usos.map((ejercicio) => ejercicio.nombre).join(", ") : "Ningún ejercicio lo usa"),
      erroresEquipo.has(equipo.id) ? crear("p", { role: "alert" }, erroresEquipo.get(equipo.id)) : null),
    pidiendoMotivo
      ? crear("form", { className: "equipo-accion", "data-cambiar-estado": equipo.id },
        crear("label", { htmlFor: idMotivo }, "Motivo opcional",
          crear("input", { id: idMotivo, name: "motivo", maxLength: 500, autocomplete: "off" })),
        crear("button", { type: "submit", className: "boton-tinta" }, "Confirmar fuera de servicio"),
        crear("button", { type: "button", className: "boton-borde", "data-cancelar-motivo": equipo.id }, "Cancelar"))
      : fuera
        ? crear("form", { className: "equipo-accion", "data-cambiar-estado": equipo.id },
          crear("button", { type: "submit", className: "boton-tinta" }, "Marcar disponible"))
        : crear("div", { className: "equipo-accion" },
          crear("button", { type: "button", className: "boton-borde", "data-pedir-motivo": equipo.id }, "Marcar fuera de servicio")));
}

function renglonDeAlternativa(ejercicio, id, indice) {
  const alternativa = porId.get(id);
  const fuera = alternativa?.estado_equipo === "fuera_de_servicio";
  const nombre = alternativa?.nombre ?? "Ejercicio";
  return crear("li", { "data-alternativa": id },
    crear("span", { className: "alternativa-orden" }, String(indice + 1)),
    crear("span", { className: "alternativa-nombre" }, nombre,
      crear("span", { className: "nota-suave" }, ` ${nombreDeEquipo(alternativa?.equipo ?? "")}${fuera ? " · fuera de servicio" : ""}`)),
    crear("span", { className: "alternativa-botones" },
      crear("button", { type: "button", className: "boton-icono", "data-mover": ejercicio.id, "data-indice": indice, "data-salto": -1, disabled: indice === 0, "aria-label": `Subir ${nombre}` }, "↑"),
      crear("button", { type: "button", className: "boton-icono", "data-mover": ejercicio.id, "data-indice": indice, "data-salto": 1, disabled: indice === ejercicio.alternativas.length - 1, "aria-label": `Bajar ${nombre}` }, "↓"),
      crear("button", { type: "button", className: "boton-icono", "data-quitar": ejercicio.id, "data-indice": indice, "aria-label": `Quitar ${nombre}` }, "×")));
}

function filaDeEjercicio(ejercicio) {
  const candidatos = candidatosDeAlternativa(ejercicio, catalogo);
  const idSelect = `agregar-${ejercicio.id}`;
  const sinSalida = sinAlternativaDisponible(ejercicio, porId);
  return crear("li", { className: "fila-ejercicio", "data-ejercicio": ejercicio.id },
    crear("div", { className: "ejercicio-cabecera" },
      crear("h3", {}, ejercicio.nombre),
      crear("p", { className: "nota-suave" }, `${ejercicio.patron_movimiento} · ${nombreDeEquipo(ejercicio.equipo)}`)),
    ejercicio.alternativas.length
      ? crear("ol", { className: "alternativas" }, ejercicio.alternativas.map((id, indice) => renglonDeAlternativa(ejercicio, id, indice)))
      : null,
    sinSalida
      ? crear("p", { className: "aviso-sin-alternativa" }, ejercicio.alternativas.length ? "Sus alternativas no están disponibles." : "Sin alternativa: si su equipo sale de servicio, el ejercicio queda no disponible.")
      : null,
    erroresEjercicio.has(ejercicio.id) ? crear("p", { role: "alert" }, erroresEjercicio.get(ejercicio.id)) : null,
    candidatos.length
      ? crear("form", { className: "agregar-alternativa", "data-agregar": ejercicio.id },
        crear("label", { htmlFor: idSelect, className: "solo-lector" }, `Agregar alternativa a ${ejercicio.nombre}`),
        crear("select", { id: idSelect, name: "alternativa" },
          crear("option", { value: "" }, "Agregar alternativa…"),
          candidatos.map(({ candidato, motivo }) => crear("option", { value: candidato.id, disabled: Boolean(motivo) }, motivo ? `${candidato.nombre} (${motivo})` : candidato.nombre))),
        crear("button", { type: "submit", className: "boton-borde" }, "Agregar"))
      : null);
}

function dibujar() {
  const fuera = equipos.filter((equipo) => equipo.estado === "fuera_de_servicio").length;
  $("[data-resumen-equipos]").textContent = fuera === 0 ? "Todos disponibles." : fuera === 1 ? "1 fuera de servicio." : `${fuera} fuera de servicio.`;
  $("[data-equipos]").replaceChildren(...equipos.map(filaDeEquipo));
  $("[data-ejercicios]").replaceChildren(...catalogo.map(filaDeEjercicio));
}

// Tras redibujar, el foco vuelve al control equivalente para no perder el lugar con el teclado.
function conFoco(selector, accion) {
  accion();
  (document.querySelector(selector) ?? document.querySelector("[data-estado]"))?.focus?.();
}

async function cambiarEstado(formulario) {
  const id = formulario.dataset.cambiarEstado;
  const equipo = equipos.find((actual) => actual.id === id);
  const estado = equipo.estado === "fuera_de_servicio" ? "disponible" : "fuera_de_servicio";
  const motivo = formulario.elements.motivo?.value.trim();
  formulario.querySelector("button[type=submit]").disabled = true;
  try {
    const respuesta = await enviar(`/api/equipos/${id}/estado`, { estado, ...(motivo ? { motivo } : {}) });
    equipos = equipos.map((actual) => (actual.id === id ? respuesta.equipo : actual));
    indexar();
    erroresEquipo.delete(id);
    confirmando = null;
    $("[data-estado]").textContent = `${nombreDeEquipo(equipo.nombre)}: ${estado === "disponible" ? "disponible" : "fuera de servicio"}.`;
  } catch (error) {
    erroresEquipo.set(id, error.codigo === "estado_sin_cambio" ? "Otra persona ya hizo este cambio: la lista se actualizó." : error.message);
    if (error.codigo === "estado_sin_cambio") {
      equipos = (await llamarApi("/api/equipos")).equipos;
      indexar();
      confirmando = null;
    }
  }
  conFoco(`[data-equipo="${equipo.nombre}"] button`, dibujar);
}

async function guardarAlternativas(ejercicioId, alternativas, selectorFoco) {
  try {
    const { ejercicio } = await enviar(`/api/ejercicios/${ejercicioId}/alternativas`, { alternativas });
    catalogo = catalogo.map((actual) => (actual.id === ejercicioId ? { ...actual, alternativas: ejercicio.alternativas } : actual));
    indexar();
    erroresEjercicio.delete(ejercicioId);
    $("[data-estado]").textContent = `Alternativas guardadas: ${porId.get(ejercicioId).nombre}.`;
  } catch (error) {
    erroresEjercicio.set(ejercicioId, mensajeLegible(error.message, porId));
  }
  conFoco(selectorFoco, dibujar);
}

function prepararEventos() {
  $("[data-contenido]").addEventListener("submit", (evento) => {
    evento.preventDefault();
    const formulario = evento.target;
    if (formulario.dataset.cambiarEstado) cambiarEstado(formulario);
    if (formulario.dataset.agregar) {
      const elegida = formulario.elements.alternativa.value;
      if (!elegida) return;
      const ejercicio = porId.get(formulario.dataset.agregar);
      guardarAlternativas(ejercicio.id, [...ejercicio.alternativas, elegida], `[data-agregar="${ejercicio.id}"] select`);
    }
  });
  $("[data-contenido]").addEventListener("click", (evento) => {
    const pedir = evento.target.closest("[data-pedir-motivo]");
    if (pedir) {
      confirmando = pedir.dataset.pedirMotivo;
      conFoco(`[data-cambiar-estado="${confirmando}"] input`, dibujar);
      return;
    }
    const cancelar = evento.target.closest("[data-cancelar-motivo]");
    if (cancelar) {
      confirmando = null;
      conFoco(`[data-pedir-motivo="${cancelar.dataset.cancelarMotivo}"]`, dibujar);
      return;
    }
    const mover = evento.target.closest("[data-mover]");
    if (mover) {
      const ejercicio = porId.get(mover.dataset.mover);
      const indice = Number(mover.dataset.indice);
      const salto = Number(mover.dataset.salto);
      guardarAlternativas(ejercicio.id, moverEnLista(ejercicio.alternativas, indice, salto),
        `[data-ejercicio="${ejercicio.id}"] [data-mover][data-indice="${indice + salto}"][data-salto="${salto}"]:not(:disabled), [data-ejercicio="${ejercicio.id}"] [data-mover][data-indice="${indice + salto}"]`);
    }
    const quitar = evento.target.closest("[data-quitar]");
    if (quitar) {
      const ejercicio = porId.get(quitar.dataset.quitar);
      guardarAlternativas(ejercicio.id, ejercicio.alternativas.filter((_, indice) => indice !== Number(quitar.dataset.indice)), `[data-agregar="${ejercicio.id}"] select`);
    }
  });
}

async function iniciar() {
  const usuario = await exigirRol(["entrenador", "administracion"]);
  if (!usuario) return;
  prepararBarra(usuario);
  prepararEventos();
  const [respuestaEquipos, respuestaEjercicios] = await Promise.all([llamarApi("/api/equipos"), llamarApi("/api/ejercicios")]);
  equipos = respuestaEquipos.equipos;
  catalogo = respuestaEjercicios.ejercicios;
  indexar();
  dibujar();
  $("[data-contenido]").hidden = false;
  $("[data-estado]").textContent = "";
}

iniciar().catch((error) => {
  $("[data-estado]").textContent = "";
  $("[data-error]").textContent = error.message;
});
