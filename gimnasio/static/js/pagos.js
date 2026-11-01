import { llamarApi } from "@comun/api.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { formatearCedula, formatearGuaranies, formatearFecha } from "@comun/formatos.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
let socios = [];
let tipos = [];
let pendiente;
let enCurso = false;
let actualizarLista = async () => {};
const socioFijado = new URLSearchParams(location.search).get("socio");

function buscar() {
  const texto = $("#buscar").value.trim().toLocaleLowerCase("es");
  const cedula = texto.replace(/[. ]/g, "");
  const anterior = $("#socio").value;
  const encontrados = socios.filter((socio) => socioFijado ? socio.id === socioFijado : socio.nombre.toLocaleLowerCase("es").includes(texto) || (cedula && socio.cedula.includes(cedula)));
  $("#socio").replaceChildren(crear("option", { value: "" }, "Elegí un socio"), ...encontrados.map((socio) => crear("option", { value: socio.id }, `${socio.nombre} · ${formatearCedula(socio.cedula)}`)));
  if (encontrados.some((socio) => socio.id === anterior)) $("#socio").value = anterior;
  if (socioFijado) {
    $("#socio").value = socioFijado;
    $("#buscar").disabled = true;
  }
  $("[data-socios-estado]").textContent = encontrados.length ? `${encontrados.length} socios encontrados.` : "No hay socios para esa búsqueda.";
}

async function cargar() {
  if (pendiente) return;
  $("[data-pago]").hidden = true;
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando socios y tipos de membresía…";
  try {
    const [personas, catalogo] = await Promise.all([llamarApi("/api/pagos/socios"), llamarApi("/api/tipos-membresia")]);
    socios = personas.socios;
    tipos = catalogo.tipos.filter((tipo) => !tipo.archivado);
    buscar();
    $("#tipo").replaceChildren(crear("option", { value: "" }, "Elegí un tipo de membresía"), ...tipos.map((tipo) => crear("option", { value: tipo.id }, `${tipo.nombre} · ${tipo.duracion_dias} días · ${formatearGuaranies(tipo.precio)}`)));
    $("[data-precio]").textContent = "";
    $("[data-pago]").hidden = !socios.length || !tipos.length;
    $("[data-estado]").textContent = !tipos.length ? "No hay tipos de membresía disponibles. Administración debe configurar uno." : !socios.length ? "No hay socios activos." : "";
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
  }
}

async function registrar(evento) {
  evento.preventDefault();
  if (pendiente) return;
  const formulario = evento.target;
  const cuerpo = Object.fromEntries(new FormData(formulario));
  if (socioFijado) cuerpo.socio_id = socioFijado;
  if (cuerpo.monto === "") delete cuerpo.monto;
  else cuerpo.monto = Number(cuerpo.monto);
  pendiente = { cuerpo, clave: crypto.randomUUID() };
  await enviar();
}

async function enviar() {
  if (enCurso || !pendiente) return;
  enCurso = true;
  if (socioFijado && window.parent !== window) window.parent.postMessage({ tipo: "pago-en-curso" }, location.origin);
  const formulario = $("[data-pago]");
  const operacion = pendiente;
  $("[data-reintentar-pago]").hidden = true;
  formulario.querySelector("fieldset").disabled = true;
  $("[data-recargar]").disabled = true;
  $("[data-estado]").textContent = "Registrando pago y renovando membresía…";
  $("[data-error]").textContent = "";
  $("[data-resultado]").textContent = "";
  try {
    const pago = await llamarApi("/api/pagos", { metodo: "POST", cuerpo: operacion.cuerpo, clave: operacion.clave });
    pendiente = null;
    if (socioFijado && window.parent !== window) window.parent.postMessage({ tipo: "pago-registrado" }, location.origin);
    formulario.reset();
    buscar();
    $("[data-precio]").textContent = "";
    $("[data-resultado]").textContent = `Pago registrado: ${formatearGuaranies(pago.monto)}. Membresía del ${formatearFecha(pago.membresia.desde)} al ${formatearFecha(pago.membresia.hasta)}.`;
    await actualizarLista();
  } catch (error) {
    // La conexión perdida, un error del servidor o una solicitud en curso
    // requieren resolver el mismo pago antes de permitir otro.
    if (error.estadoHttp > 0 && error.estadoHttp < 500 && error.codigo !== "solicitud_en_curso") pendiente = null;
    $("[data-error]").textContent = error.message;
  } finally {
    enCurso = false;
    if (!pendiente && socioFijado && window.parent !== window) window.parent.postMessage({ tipo: "pago-libre" }, location.origin);
    $("[data-estado]").textContent = pendiente ? "No se confirmó el pago. Reintentá el mismo pago antes de registrar otro." : "";
    formulario.querySelector("fieldset").disabled = Boolean(pendiente);
    $("[data-recargar]").disabled = Boolean(pendiente);
    $("[data-reintentar-pago]").hidden = !pendiente;
  }
}

async function iniciar() {
  const usuario = await exigirRol(["recepcion", "administracion"]);
  if (!usuario) return;
  prepararBarra(usuario);
  if (socioFijado && window.parent !== window) document.querySelector("header").hidden = true;
  $("[data-solo-recepcion]").hidden = usuario.rol !== "recepcion";
  $("#buscar").addEventListener("input", buscar);
  $("#tipo").addEventListener("change", () => {
    const tipo = tipos.find((tipo) => tipo.id === $("#tipo").value);
    $("[data-precio]").textContent = tipo ? `Precio: ${formatearGuaranies(tipo.precio)} · Duración: ${tipo.duracion_dias} días` : "";
  });
  $("[data-pago]").addEventListener("submit", registrar);
  $("[data-reintentar-pago]").addEventListener("click", enviar);
  $("[data-recargar]").addEventListener("click", cargar);
  await cargar();
  const hoy = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Asuncion", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  $("[data-filtro-pagos]").elements.desde.value = hoy;
  $("[data-filtro-pagos]").elements.hasta.value = hoy;
  $("[data-filtro-pagos]").addEventListener("submit", (evento) => { evento.preventDefault(); cargarLista(); });
  actualizarLista = cargarLista;
  await cargarLista();
}

async function cargarLista() {
  $("[data-lista-estado]").textContent = "Cargando pagos…";
  $("[data-lista-error]").textContent = "";
  $("[data-total-pagos]").textContent = "";
  $("[data-lista-pagos]").replaceChildren();
  try {
    const parametros = new URLSearchParams(new FormData($("[data-filtro-pagos]")));
    const { pagos, total } = await llamarApi(`/api/pagos?${parametros}`);
    $("[data-total-pagos]").textContent = `Total sin anulados: ${formatearGuaranies(total)}`;
    $("[data-lista-estado]").textContent = pagos.length ? `${pagos.length} pagos.` : "No hay pagos en estas fechas.";
    for (const pago of pagos) {
      const fecha = new Intl.DateTimeFormat("es-PY", { timeZone: "America/Asuncion", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(pago.registrado_en));
      const fila = crear("article", {}, crear("h3", {}, pago.socio), crear("p", {}, `${pago.tipo} · ${pago.medio} · ${formatearGuaranies(pago.monto)}`), crear("p", {}, `${fecha} · ${pago.autor}`));
      if (pago.anulacion) fila.append(crear("p", {}, `Anulado: ${pago.anulacion.motivo}`));
      else {
        const motivo = crear("textarea", { name: "motivo", required: true, maxLength: 500 });
        const boton = crear("button", { type: "submit" }, "Anular pago");
        const estado = crear("p", { role: "status" });
        const formulario = crear("form", {}, crear("label", {}, "Motivo de anulación", motivo), boton, estado);
        let pendiente;
        formulario.addEventListener("submit", async (evento) => {
          evento.preventDefault();
          pendiente ??= { cuerpo: { motivo: motivo.value }, clave: crypto.randomUUID() };
          boton.disabled = true;
          motivo.disabled = true;
          estado.textContent = "Anulando pago…";
          try {
            await llamarApi(`/api/pagos/${pago.id}/anular`, { metodo: "POST", ...pendiente });
            await cargarLista();
          } catch (error) {
            if (error.estadoHttp > 0 && error.estadoHttp < 500 && error.codigo !== "solicitud_en_curso") pendiente = null;
            estado.textContent = error.message;
            boton.textContent = pendiente ? "Reintentar la misma anulación" : "Anular pago";
            motivo.disabled = Boolean(pendiente);
          } finally { boton.disabled = false; }
        });
        fila.append(formulario);
      }
      $("[data-lista-pagos]").append(fila);
    }
  } catch (error) {
    $("[data-lista-estado]").textContent = "";
    $("[data-lista-error]").textContent = error.message;
  }
}
iniciar().catch((error) => { $("[data-estado]").textContent = ""; $("[data-error]").textContent = error.message; });
