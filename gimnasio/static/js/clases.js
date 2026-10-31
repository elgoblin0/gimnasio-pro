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
let socios = null;
let consultaAgenda = 0;
let enCurso = false;

function elegirSocios() {
  const seleccion = $("[data-socio]").value;
  const buscar = $("[data-buscar-socio]").value.trim().toLocaleLowerCase();
  const cedula = buscar.replace(/[. ]/g, "");
  const encontrados = socios.filter((socio) => socio.id === seleccion || socio.nombre.toLocaleLowerCase().includes(buscar)
    || (cedula && socio.cedula.includes(cedula)));
  $("[data-socio]").replaceChildren(crear("option", { value: "" }, "Elegí un socio"), ...encontrados
    .map((socio) => crear("option", { value: socio.id }, socio.nombre)));
  $("[data-socio]").value = seleccion;
  $("[data-socios-estado]").textContent = encontrados.length ? `${encontrados.length} socios encontrados.` : "No hay socios para esa búsqueda.";
}

async function verReservas(fila, boton) {
  boton.disabled = true;
  const panel = $("[data-lista-reservas]");
  panel.hidden = false;
  panel.textContent = "Cargando reservas…";
  try {
    const { reservas } = await llamarApi(`/api/clases/${fila.clase_id}/${fila.fecha}/reservas`);
    panel.replaceChildren(crear("h3", {}, `${fila.clase} · ${fecha(fila.fecha)} ${fila.hora_inicio}`),
      reservas.length ? crear("ol", {}, ...reservas.map((reserva) => crear("li", {},
        `${reserva.nombre} · ${reserva.estado === "con_lugar" ? "Con lugar" : `En espera · Posición ${reserva.posicion}`}`)))
        : crear("p", {}, "Todavía no hay reservas."));
  } catch (error) {
    panel.textContent = error.message;
  } finally {
    boton.disabled = false;
  }
}

function dibujarOcurrencia(fila) {
  const elemento = crear("li", {},
    `${fecha(fila.fecha)} · ${fila.hora_inicio} · ${fila.clase} · ${fila.entrenador} · ${fila.duracion_minutos} minutos · Cupo: ${fila.cupo} · Libres: ${fila.libres} · En espera: ${fila.espera} `);
  if (fila.reserva) elemento.append(crear("span", {}, fila.reserva.estado === "con_lugar"
    ? "Con lugar " : `En espera · Posición ${fila.reserva.posicion} `));
  if (usuario.rol === "socio" || usuario.rol === "recepcion") {
    const reserva = fila.reserva;
    elemento.append(crear("button", { type: "button", disabled: usuario.rol === "recepcion" && !$("[data-socio]").value,
      onclick: (evento) => escribir(reserva ? `/api/clases/reservas/${reserva.id}/cancelar` : "/api/clases/reservas", "POST",
        reserva ? undefined : { clase_id: fila.clase_id, fecha: fila.fecha,
          ...(usuario.rol === "recepcion" ? { socio_id: $("[data-socio]").value } : {}) }, evento.currentTarget),
    }, reserva ? "Cancelar reserva" : "Reservar"));
  }
  if (["entrenador", "recepcion", "administracion"].includes(usuario.rol)) {
    elemento.append(crear("button", { type: "button", onclick: (evento) => verReservas(fila, evento.currentTarget) }, "Ver reservas"));
  }
  return elemento;
}

function nueva() {
  claseId = null;
  formulario.reset();
  $("[data-titulo-formulario]").textContent = "Nueva clase";
}

async function cargar() {
  const consulta = ++consultaAgenda;
  $("[data-agenda]").replaceChildren();
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando clases…";
  $("[data-reintentar]").hidden = true;
  try {
    if (usuario.rol === "recepcion" && socios === null) {
      ({ socios } = await llamarApi("/api/visitas/socios"));
      elegirSocios();
      $("[data-recepcion]").hidden = false;
    }
    const socioId = usuario.rol === "recepcion" ? $("[data-socio]").value : "";
    const agenda = await llamarApi(`/api/clases/agenda${socioId ? `?socio_id=${encodeURIComponent(socioId)}` : ""}`);
    if (consulta !== consultaAgenda) return;
    $("[data-rango]").textContent = `${fecha(agenda.desde)} al ${fecha(agenda.hasta)} · ${agenda.zona_horaria}`;
    $("[data-vacio]").hidden = agenda.ocurrencias.length > 0;
    $("[data-agenda]").replaceChildren(...agenda.ocurrencias.map(dibujarOcurrencia));
    $("[data-lista-reservas]").hidden = true;
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
    if (consulta !== consultaAgenda) return;
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
    $("[data-reintentar]").hidden = false;
  }
}

async function escribir(ruta, metodo, cuerpo, boton) {
  if (enCurso) return;
  const huella = JSON.stringify([ruta, metodo, cuerpo]);
  if (pendiente && pendiente.huella !== huella) {
    $("[data-error]").textContent = "Reintentá la operación pendiente antes de continuar.";
    return;
  }
  enCurso = true;
  boton.disabled = true;
  $("[data-reintentar-operacion]").hidden = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Guardando…";
  if (!pendiente) pendiente = { ruta, metodo, cuerpo, huella, clave: crypto.randomUUID() };
  try {
    await llamarApi(ruta, { metodo, cuerpo, clave: pendiente.clave });
    pendiente = null;
    nueva();
    await cargar();
  } catch (error) {
    if (error.estadoHttp > 0 && error.estadoHttp < 500 && error.codigo !== "solicitud_en_curso") pendiente = null;
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
  } finally {
    enCurso = false;
    $("[data-reintentar-operacion]").hidden = !pendiente;
    if (pendiente) $("[data-estado]").textContent = "No se confirmó la operación. Reintentá antes de continuar.";
    boton.disabled = false;
  }
}

async function iniciar() {
  usuario = await exigirRol(["socio", "recepcion", "entrenador", "administracion"]);
  if (!usuario) return;
  prepararBarra(usuario);
  if (usuario.rol === "recepcion") {
    $("[data-buscar-socio]").addEventListener("input", elegirSocios);
    $("[data-socio]").addEventListener("change", cargar);
  }
  $("[data-reintentar]").addEventListener("click", cargar);
  $("[data-reintentar-operacion]").addEventListener("click", (evento) => {
    if (pendiente) escribir(pendiente.ruta, pendiente.metodo, pendiente.cuerpo, evento.currentTarget);
  });
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
