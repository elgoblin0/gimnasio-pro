import { llamarApi } from "@comun/api.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { registrarPwa } from "@comun/pwa.js";
import { crearSondeo } from "@comun/sondeo.js";
import { anuncioDeCambio, cambiosDeAgenda, claveOcurrencia, fechaLegible as fecha, marcasDeCupo, semanasDeAgenda, textoReserva } from "./clases-agenda.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
const formulario = $("[data-formulario]");
const dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const DURACION_VUELO = 720;
let usuario;
let claseId = null;
let pendiente;
let socios = null;
let consultaAgenda = 0;
let enCurso = false;
let sondeo;
let filasAgenda = null;
let formaAgenda = "";
let focoOperacion = null;
let cancelando = null;
const tarjetas = new Map();
const firmas = new Map();

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
  const contenido = $("[data-lista-contenido]");
  contenido.replaceChildren(crear("p", { role: "status" }, "Cargando reservas…"));
  $("[data-lista-reservas]").showModal();
  try {
    const { reservas } = await llamarApi(`/api/clases/${fila.clase_id}/${fila.fecha}/reservas`);
    contenido.replaceChildren(crear("h3", {}, `${fila.clase} · ${fecha(fila.fecha)} ${fila.hora_inicio}`),
      reservas.length ? crear("ol", {}, ...reservas.map((reserva) => crear("li", {},
        `${reserva.nombre} · ${textoReserva(reserva)}`)))
        : crear("p", {}, "Todavía no hay reservas."));
  } catch (error) {
    contenido.replaceChildren(crear("p", { role: "alert" }, error.message));
  } finally {
    boton.disabled = false;
  }
}

function pedirMotivo(fila, boton) {
  cancelando = { fila, boton };
  $("[data-cancelar-detalle]").textContent = `${fila.clase} · ${fecha(fila.fecha)} ${fila.hora_inicio}`;
  $("[data-formulario-cancelar]").reset();
  $("[data-dialogo-cancelar]").showModal();
}

function llenarBarra(proporcion) {
  const relleno = crear("span");
  relleno.style.width = `${proporcion * 100}%`;
  return relleno;
}

function dibujarMarcas(fila, cambio) {
  const { asientos, proporcion, espera, restoEspera } = marcasDeCupo(fila);
  const cupo = asientos
    ? crear("span", { className: "marcas-cupo" }, ...asientos.map((marca, indice) => crear("span", {
      className: "marca", "data-marca": marca, "data-asiento": String(indice),
      "data-entra": cambio?.entran.includes(indice) ? "true" : undefined,
      "data-sale": cambio?.salen.includes(indice) ? "true" : undefined,
    })))
    : crear("span", { className: "barra-cupo" }, llenarBarra(proporcion));
  return crear("div", { className: "marcas", "aria-hidden": "true" }, cupo, espera.length > 0 && crear("span", { className: "marcas-espera" },
    ...espera.map((marca) => crear("span", { className: "marca marca-espera", "data-marca": marca })),
    restoEspera > 0 && crear("span", { className: "marcas-resto" }, `+${restoEspera}`)));
}

function dibujarOcurrencia(fila, cambio) {
  const reserva = fila.reserva;
  const clave = [fila.clase_id, fila.fecha];
  const detalleId = `ocurrencia-${fila.clase_id}-${fila.fecha}`;
  const accion = (texto, nombre, clase, alPulsar, deshabilitado) => crear("button", {
    type: "button", className: clase, "aria-describedby": detalleId, disabled: deshabilitado,
    "data-foco-agenda": JSON.stringify([...clave, nombre]), onclick: alPulsar,
  }, texto);
  const elemento = crear("li", {
    className: "ocurrencia", tabIndex: -1, "data-foco-agenda": JSON.stringify([...clave, "ocurrencia"]),
    "data-cancelada": fila.cancelada ? "true" : undefined,
    "data-reserva": !fila.cancelada && reserva ? reserva.estado : undefined,
    "data-cambio": cambio?.propio ?? (cambio?.cancelada ? "cancelada" : undefined),
  },
  crear("span", { className: "solo-lector", id: detalleId }, `${fila.clase}, ${fecha(fila.fecha)}, ${fila.hora_inicio}`),
  crear("p", { className: "ocurrencia-hora" }, fila.hora_inicio, crear("span", { className: "nota-suave" }, ` ${fila.duracion_minutos} minutos`)),
  crear("p", { className: "ocurrencia-nombre" }, fila.clase),
  crear("p", { className: "ocurrencia-entrenador nota-suave" }, fila.entrenador),
  dibujarMarcas(fila, cambio),
  crear("p", { className: "ocurrencia-cifras nota-suave", "data-cambia": cambio?.cifras ? "true" : undefined },
    crear("span", {}, `Cupo: ${fila.cupo}`), " ", crear("span", {}, `Libres: ${fila.libres}`), " ", fila.espera > 0 && crear("span", {}, `En espera: ${fila.espera}`)));
  if (fila.cancelada) {
    elemento.append(crear("strong", { className: "sello-agenda", "data-sello": "cancelada" }, "Ocurrencia cancelada"));
    return elemento;
  }
  if (reserva) elemento.append(crear("span", { className: "sello-agenda", "data-sello": reserva.estado }, textoReserva(reserva)));
  else if (fila.libres === 0) elemento.append(crear("p", { className: "ocurrencia-sin-lugar" }, "Sin lugar: se reserva en lista de espera."));
  if (fila.empezada) elemento.append(crear("p", { className: "nota-suave" }, "Ya empezó."));
  const acciones = [];
  if (!fila.empezada && (usuario.rol === "socio" || usuario.rol === "recepcion")) {
    acciones.push(accion(reserva ? "Cancelar reserva" : "Reservar", reserva ? "cancelar_reserva" : "reservar", reserva ? "boton-borde" : "boton-reservar",
      (evento) => escribir(reserva ? `/api/clases/reservas/${reserva.id}/cancelar` : "/api/clases/reservas", "POST",
        reserva ? undefined : { clase_id: fila.clase_id, fecha: fila.fecha,
          ...(usuario.rol === "recepcion" ? { socio_id: $("[data-socio]").value } : {}) }, evento.currentTarget),
      usuario.rol === "recepcion" && !$("[data-socio]").value));
  }
  if (["entrenador", "recepcion", "administracion"].includes(usuario.rol)) {
    acciones.push(accion("Ver reservas", "ver_reservas", "boton-enlace", (evento) => verReservas(fila, evento.currentTarget)));
  }
  if (!fila.empezada && ["recepcion", "administracion"].includes(usuario.rol)) {
    acciones.push(accion("Cancelar ocurrencia", "cancelar_ocurrencia", "boton-enlace", (evento) => pedirMotivo(fila, evento.currentTarget)));
  }
  elemento.append(crear("div", { className: "ocurrencia-acciones" }, ...acciones));
  return elemento;
}

function dibujarSemanas(datos, cambios) {
  tarjetas.clear();
  const cambioDe = new Map(cambios.map((cambio) => [cambio.clave, cambio]));
  const tarjeta = (fila) => {
    const elemento = dibujarOcurrencia(fila, cambioDe.get(claveOcurrencia(fila)));
    tarjetas.set(claveOcurrencia(fila), elemento);
    return elemento;
  };
  return semanasDeAgenda(datos).map((semana) => crear("section", { className: "semana", "aria-label": semana.titulo },
    crear("h3", { className: "semana-titulo" }, semana.titulo, crear("span", { className: "nota-suave" }, ` ${fecha(semana.desde)} al ${fecha(semana.hasta)}`)),
    crear("div", { className: "semana-dias" }, ...semana.dias.map((dia) => crear("div", { className: "dia", "data-sin-clases": dia.ocurrencias.length ? undefined : "true" },
      crear("h4", { className: "dia-titulo" }, dia.nombre, crear("span", { className: "nota-suave" }, ` ${fecha(dia.fecha)}`)),
      dia.ocurrencias.length ? crear("ol", { className: "dia-ocurrencias" }, ...dia.ocurrencias.map(tarjeta))
        : crear("p", { className: "dia-vacio nota-suave" }, "Sin clases"))))));
}

const firmaDe = (fila) => JSON.stringify([fila, usuario.rol === "recepcion" && !$("[data-socio]").value]);
const movimientoReducido = () => !globalThis.matchMedia || globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Con la misma forma se cambian solo las tarjetas distintas: el resto conserva foco y lectura.
function pintarAgenda(datos, animar) {
  const lista = $("[data-agenda]");
  const forma = datos.ocurrencias.map((fila) => `${claveOcurrencia(fila)}|${fila.hora_inicio}`).sort().join();
  const cambios = cambiosDeAgenda(filasAgenda, datos.ocurrencias);
  const conAnimacion = animar && !movimientoReducido() ? cambios : [];
  const foco = lista.contains(document.activeElement) ? document.activeElement.dataset.focoAgenda : focoOperacion;
  focoOperacion = null;
  const origenes = medirEspera(conAnimacion);
  if (filasAgenda !== null && forma === formaAgenda) {
    const cambioDe = new Map(conAnimacion.map((cambio) => [cambio.clave, cambio]));
    for (const fila of datos.ocurrencias) {
      const clave = claveOcurrencia(fila);
      if (firmas.get(clave) === firmaDe(fila)) continue;
      const nueva = dibujarOcurrencia(fila, cambioDe.get(clave));
      tarjetas.get(clave).replaceWith(nueva);
      tarjetas.set(clave, nueva);
    }
  } else {
    lista.replaceChildren(...(datos.ocurrencias.length ? dibujarSemanas(datos, conAnimacion) : []));
    if (!datos.ocurrencias.length) tarjetas.clear();
  }
  formaAgenda = forma;
  firmas.clear();
  for (const fila of datos.ocurrencias) firmas.set(claveOcurrencia(fila), firmaDe(fila));
  $("[data-rango]").textContent = `${fecha(datos.desde)} al ${fecha(datos.hasta)} · ${datos.zona_horaria}`;
  $("[data-vacio]").hidden = datos.ocurrencias.length > 0;
  $("[data-leyenda]").hidden = !datos.ocurrencias.length;
  if (foco) restaurarFoco(lista, foco);
  if (animar) anunciar(datos, cambios);
  volarDesdeEspera(conAnimacion, origenes);
  filasAgenda = datos.ocurrencias;
}

// Si la acción con foco ya no existe, el foco queda en la tarjeta: pasarlo a otro botón podría cancelar con un Enter de más.
function restaurarFoco(lista, foco) {
  const boton = [...lista.querySelectorAll("button")].find((candidato) => candidato.dataset.focoAgenda === foco && !candidato.disabled);
  if (boton) { boton.focus({ preventScroll: true }); return; }
  const [claseFoco, fechaFoco] = JSON.parse(foco);
  tarjetas.get(`${claseFoco}|${fechaFoco}`)?.focus({ preventScroll: true });
}

function anunciar(datos, cambios) {
  const porClave = new Map(datos.ocurrencias.map((fila) => [claveOcurrencia(fila), fila]));
  const voz = usuario.rol === "socio" ? "propio" : "socio";
  const frases = cambios.map((cambio) => anuncioDeCambio(porClave.get(cambio.clave), cambio, voz)).filter(Boolean);
  if (frases.length) $("[data-anuncio]").textContent = frases.join(" ");
}

function medirEspera(cambios) {
  const origenes = new Map();
  for (const cambio of cambios) {
    if (!cambio.vuelos.length) continue;
    const marcas = tarjetas.get(cambio.clave)?.querySelectorAll(".marca-espera") ?? [];
    origenes.set(cambio.clave, [...marcas].map((marca) => marca.getBoundingClientRect()));
  }
  return origenes;
}

// La marca nace en su asiento y se anima desde donde estaba en la lista de espera.
function volarDesdeEspera(cambios, origenes) {
  for (const cambio of cambios) {
    for (const { desdeEspera, asiento } of cambio.vuelos) {
      const origen = origenes.get(cambio.clave)?.[desdeEspera];
      const destino = tarjetas.get(cambio.clave)?.querySelector(`[data-asiento="${asiento}"]`);
      if (!origen || !destino) continue;
      const llegada = destino.getBoundingClientRect();
      destino.dataset.vuela = "true";
      destino.animate([
        { translate: `${origen.left - llegada.left}px ${origen.top - llegada.top}px`, scale: 1.4 },
        { translate: "0 0", scale: 1 },
      ], { duration: DURACION_VUELO, easing: "cubic-bezier(.22, 1, .36, 1)" }).finished.finally(() => delete destino.dataset.vuela);
    }
  }
}

function nueva() {
  claseId = null;
  formulario.reset();
  $("[data-titulo-formulario]").textContent = "Nueva clase";
}

async function cargar(opciones) {
  sondeo?.detener();
  const consulta = ++consultaAgenda;
  const conservar = opciones?.conservar === true;
  if (!conservar) {
    filasAgenda = null;
    tarjetas.clear();
    $("[data-agenda]").replaceChildren();
    $("[data-estado]").textContent = "Cargando clases…";
  }
  $("[data-error]").textContent = "";
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
    pintarAgenda(agenda, conservar);
    if (["socio", "recepcion"].includes(usuario.rol)) {
      sondeo = crearSondeo({
        url: `/api/clases/agenda${socioId ? `?socio_id=${encodeURIComponent(socioId)}` : ""}`,
        puedeConsultar: () => !enCurso && !pendiente && !$("[data-lista-reservas]").open && !$("[data-dialogo-cancelar]").open,
        alCambiar: (datos) => {
          if (consulta !== consultaAgenda) return;
          pintarAgenda(datos, true);
          $("[data-error]").textContent = "";
        },
        alFallar: () => { $("[data-error]").textContent = "No se pudo actualizar la agenda. Se reintentará."; },
      });
    }
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
  // Deshabilitar el botón le quita el foco: se recuerda para devolverlo al redibujar o si la operación falla.
  focoOperacion = boton.dataset.focoAgenda ?? null;
  boton.disabled = true;
  $("[data-reintentar-operacion]").hidden = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Guardando…";
  if (!pendiente) pendiente = { ruta, metodo, cuerpo, huella, clave: crypto.randomUUID() };
  try {
    await llamarApi(ruta, { metodo, cuerpo, clave: pendiente.clave });
    pendiente = null;
    nueva();
    await cargar({ conservar: true });
  } catch (error) {
    if (error.estadoHttp > 0 && error.estadoHttp < 500 && error.codigo !== "solicitud_en_curso") pendiente = null;
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
  } finally {
    enCurso = false;
    $("[data-reintentar-operacion]").hidden = !pendiente;
    if (pendiente) $("[data-estado]").textContent = "No se confirmó la operación. Reintentá antes de continuar.";
    boton.disabled = false;
    if (focoOperacion) boton.focus();
    focoOperacion = null;
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
  $("[data-leyenda-propia]").hidden = usuario.rol !== "socio";
  $("[data-reintentar]").addEventListener("click", cargar);
  $("[data-reintentar-operacion]").addEventListener("click", (evento) => {
    if (pendiente) escribir(pendiente.ruta, pendiente.metodo, pendiente.cuerpo, evento.currentTarget);
  });
  $("[data-nueva]").addEventListener("click", nueva);
  $("[data-cerrar-cancelar]").addEventListener("click", () => $("[data-dialogo-cancelar]").close());
  $("[data-formulario-cancelar]").addEventListener("submit", (evento) => {
    evento.preventDefault();
    const motivo = new FormData(evento.currentTarget).get("motivo");
    if (!motivo.trim()) return;
    const { fila, boton } = cancelando;
    $("[data-dialogo-cancelar]").close();
    escribir(`/api/clases/${fila.clase_id}/${fila.fecha}/cancelar`, "POST", { motivo }, boton);
  });
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const cuerpo = Object.fromEntries(new FormData(formulario));
    for (const campo of ["dia_semana", "duracion_minutos", "cupo"]) cuerpo[campo] = Number(cuerpo[campo]);
    escribir(claseId ? `/api/clases/${claseId}` : "/api/clases", claseId ? "PUT" : "POST", cuerpo, formulario.querySelector("[type=submit]"));
  });
  await cargar();
}
iniciar().catch((error) => { $("[data-estado]").textContent = ""; $("[data-error]").textContent = error.message; });
