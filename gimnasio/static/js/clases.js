import { llamarApi } from "@comun/api.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
const formulario = $("[data-formulario]");
const dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const fecha = (valor) => valor.split("-").reverse().join("/");
let usuario;
let claseId = null;
let pendiente;

function nueva() {
  claseId = null;
  formulario.reset();
  $("[data-titulo-formulario]").textContent = "Nueva clase";
}

async function cargar() {
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando clases…";
  $("[data-reintentar]").hidden = true;
  try {
    const agenda = await llamarApi("/api/clases/agenda");
    $("[data-rango]").textContent = `${fecha(agenda.desde)} al ${fecha(agenda.hasta)} · ${agenda.zona_horaria}`;
    $("[data-vacio]").hidden = agenda.ocurrencias.length > 0;
    $("[data-agenda]").replaceChildren(...agenda.ocurrencias.map((fila) => crear("li", {},
      `${fecha(fila.fecha)} · ${fila.hora_inicio} · ${fila.clase} · ${fila.entrenador} · ${fila.duracion_minutos} minutos · Cupo: ${fila.cupo}`)));
    if (usuario.rol === "administracion") {
      const datos = await llamarApi("/api/clases");
      formulario.elements.entrenador_id.replaceChildren(...datos.entrenadores.map((entrenador) =>
        crear("option", { value: entrenador.id }, `${entrenador.nombre} ${entrenador.apellido}`)));
      $("[data-clases]").replaceChildren(...datos.clases.map((clase) => crear("li", {},
        `${clase.nombre} · ${dias[clase.dia_semana - 1]} ${clase.hora_inicio}${clase.archivada ? " · Archivada" : ""} `,
        !clase.archivada && crear("button", { type: "button", onclick: () => {
          claseId = clase.id;
          for (const campo of ["nombre", "entrenador_id", "dia_semana", "hora_inicio", "duracion_minutos", "cupo"]) formulario.elements[campo].value = clase[campo];
          $("[data-titulo-formulario]").textContent = `Editar ${clase.nombre}`;
          formulario.elements.nombre.focus();
        } }, "Editar"),
        !clase.archivada && crear("button", { type: "button", onclick: (evento) =>
          escribir(`/api/clases/${clase.id}/archivar`, "POST", undefined, evento.currentTarget) }, "Archivar"))));
      $("[data-configuracion]").hidden = false;
    }
    $("[data-estado]").textContent = "";
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
    $("[data-reintentar]").hidden = false;
  }
}

async function escribir(ruta, metodo, cuerpo, boton) {
  boton.disabled = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Guardando clase…";
  const huella = JSON.stringify([ruta, metodo, cuerpo]);
  if (pendiente?.huella !== huella) pendiente = { huella, clave: crypto.randomUUID() };
  try {
    await llamarApi(ruta, { metodo, cuerpo, clave: pendiente.clave });
    pendiente = null;
    nueva();
    await cargar();
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
  } finally {
    boton.disabled = false;
  }
}

async function iniciar() {
  usuario = await exigirRol(["socio", "recepcion", "entrenador", "administracion"]);
  if (!usuario) return;
  prepararBarra(usuario);
  $("[data-reintentar]").addEventListener("click", cargar);
  $("[data-nueva]").addEventListener("click", nueva);
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const cuerpo = Object.fromEntries(new FormData(formulario));
    for (const campo of ["dia_semana", "duracion_minutos", "cupo"]) cuerpo[campo] = Number(cuerpo[campo]);
    escribir(claseId ? `/api/clases/${claseId}` : "/api/clases", claseId ? "PUT" : "POST", cuerpo, formulario.querySelector("[type=submit]"));
  });
  await cargar();
}
iniciar().catch((error) => { $("[data-estado]").textContent = ""; $("[data-error]").textContent = error.message; });
