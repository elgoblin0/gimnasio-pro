import { llamarApi } from "@comun/api.js";
import { montarPerfil } from "./perfil-entrenamiento.js";
import { formatearCarga, formatearFechaHora } from "@comun/formatos.js";
import { crearControlDeOperacion } from "@comun/operaciones.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { registrarPwa } from "@comun/pwa.js";
import { crearSondeo } from "@comun/sondeo.js";
import { ZONAS_CUERPO } from "@comun/zonas.js";
import {
  GRUPOS_BANDEJA, antiguedad, avisosSinRevisar, contarSocios, explicacionDeAviso, motivosPorSocio, sociosConNovedad, textoFreno, textosDeMotivos,
} from "./bandeja-textos.js";

registrarPwa();

const FILAS_A_LA_VISTA = 6;
const $ = (selector) => document.querySelector(selector);
const pagina = () => new URL(location.href);
const fechaLegible = (texto) => formatearFechaHora(new Date(texto).toISOString());
const nombreDeZona = (id) => ZONAS_CUERPO.find((zona) => zona.id === id)?.nombre ?? id;

const gruposAbiertos = new Set();
const control = crearControlDeOperacion();
let catalogo = new Map();
let motivosAnteriores = null;
let gruposActuales = null;
let socioAbierto = null;
let avisosALaVista = [];
let lecturaDeSocio = 0;
let sondeo;

const nombreDeEjercicio = (id) => catalogo.get(id)?.nombre ?? null;

function filaDeSocio(socio, tipo, nuevos) {
  const motivoDelGrupo = socio.motivos.filter((motivo) => motivo.tipo === tipo).map((motivo) => motivo.fecha).sort()[0];
  return crear("li", { "data-fila-socio": socio.id, "data-nueva": nuevos.has(socio.id) ? "true" : undefined },
    crear("a", {
      className: "fila-socio",
      href: `/bandeja.html?socio=${socio.id}`,
      "aria-current": socio.id === socioAbierto ? "true" : undefined,
      "data-enlace-socio": socio.id,
    },
    crear("span", { className: "fila-nombre" }, `${socio.nombre} ${socio.apellido}`),
    crear("span", { className: "fila-antiguedad", title: fechaLegible(motivoDelGrupo) }, antiguedad(motivoDelGrupo, Date.now())),
    crear("span", { className: "fila-motivos" }, textosDeMotivos(socio.motivos).join(" · "))));
}

function dibujarGrupos(grupos, nuevos = new Set()) {
  const enFoco = document.activeElement?.dataset?.enlaceSocio;
  const botonEnFoco = document.activeElement?.dataset?.verGrupo;
  const visibles = grupos.filter((grupo) => grupo.socios.length);
  $("[data-grupos]").replaceChildren(...visibles.map((grupo) => {
    const abierto = gruposAbiertos.has(grupo.tipo);
    // Un socio abierto o recién llegado no queda escondido por el corte.
    const filas = grupo.socios.filter((socio, indice) => abierto || indice < FILAS_A_LA_VISTA || socio.id === socioAbierto || nuevos.has(socio.id));
    const ocultos = grupo.socios.length - filas.length;
    const idTitulo = `grupo-${grupo.tipo}`;
    return crear("section", { className: "grupo-bandeja", "data-grupo": grupo.tipo, "aria-labelledby": idTitulo },
      crear("h2", { id: idTitulo },
        crear("span", {}, GRUPOS_BANDEJA[grupo.tipo] ?? grupo.tipo),
        crear("span", { className: "grupo-cuenta" }, String(grupo.socios.length))),
      crear("ul", { className: "filas-socio" }, filas.map((socio) => filaDeSocio(socio, grupo.tipo, nuevos))),
      ocultos > 0 || abierto && grupo.socios.length > FILAS_A_LA_VISTA
        ? crear("button", {
          type: "button",
          className: "boton-enlace",
          "data-ver-grupo": grupo.tipo,
          "aria-expanded": String(abierto),
          textContent: abierto ? "Ver menos" : `Ver ${ocultos === 1 ? "el restante" : `los ${ocultos} restantes`}`,
        })
        : null);
  }));
  const total = contarSocios(grupos);
  $("[data-resumen]").hidden = total === 0;
  $("[data-resumen-cifra]").textContent = String(total);
  $("[data-resumen-texto]").textContent = total === 1 ? "socio requiere atención" : "socios requieren atención";
  $("[data-vacia]").hidden = total !== 0;
  if (enFoco) document.querySelector(`[data-enlace-socio="${enFoco}"]`)?.focus();
  if (botonEnFoco) document.querySelector(`[data-ver-grupo="${botonEnFoco}"]`)?.focus();
}

function alCambiarBandeja({ grupos }) {
  const novedades = motivosAnteriores ? sociosConNovedad(motivosAnteriores, grupos) : [];
  motivosAnteriores = motivosPorSocio(grupos);
  gruposActuales = grupos;
  dibujarGrupos(grupos, new Set(novedades.map((socio) => socio.id)));
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = novedades.length === 1
    ? `Novedad en la bandeja: ${novedades[0].nombre} ${novedades[0].apellido}.`
    : novedades.length ? `${novedades.length} novedades en la bandeja.` : "";
  // Un aviso nuevo del socio abierto se suma a lo que la pantalla muestra, sin borrar la nota.
  if (socioAbierto && novedades.some((socio) => socio.id === socioAbierto)) leerSocio(socioAbierto);
}

function renglonAviso(aviso) {
  const { textos, ejercicios } = explicacionDeAviso(aviso, nombreDeEjercicio);
  return crear("li", { "data-aviso": aviso.id, "data-freno": aviso.freno },
    crear("p", { className: "aviso-titulo" },
      crear("strong", {}, textoFreno(aviso.freno)),
      crear("span", { className: "nota-suave" }, fechaLegible(aviso.creado_en))),
    ejercicios.length ? crear("p", {}, ejercicios.join(", ")) : null,
    textos.map((texto) => crear("p", { className: "nota-suave" }, texto)),
    aviso.revision
      ? crear("p", { className: "aviso-revision" }, `Revisado ${fechaLegible(aviso.revision.revisada_en)}${aviso.revision.nota ? `: ${aviso.revision.nota}` : ""}`)
      : null);
}

function dibujarPrograma(programa) {
  const contenedor = $("[data-programa]");
  if (!programa) {
    contenedor.replaceChildren(crear("p", { className: "nota-suave" }, "Todavía no tiene programa. Podés armarlo desde una plantilla en el editor."));
    return;
  }
  const semanaTipo = programa.sesiones_planificadas.filter((sesion) => sesion.semana === 1);
  const sesiones = semanaTipo.length ? semanaTipo : programa.sesiones_planificadas;
  contenedor.replaceChildren(
    crear("p", { className: "nota-suave" }, [
      `Versión ${programa.version}`,
      programa.duracion_semanas ? `${programa.duracion_semanas} semanas` : sesiones.length === 1 ? "1 sesión" : `${sesiones.length} sesiones en secuencia`,
    ].join(" · ")),
    crear("ol", { className: "semana-resumen" }, sesiones.map((sesion) => crear("li", {},
      crear("strong", {}, sesion.semana === 1 ? sesion.nombre.replace(/^Semana 1 · /, "") : sesion.nombre),
      crear("span", { className: "nota-suave" }, sesion.ejercicios_planificados.map((ejercicio) => `${ejercicio.nombre} ${ejercicio.series}×`).join(" · ") || "Sin ejercicios")))),
  );
}

function renglonPrescripcion(ejercicio) {
  const detalle = [ejercicio.series ? `${ejercicio.series} series` : null, ejercicio.carga ? formatearCarga(ejercicio.carga) : null].filter(Boolean).join(" · ");
  return crear("li", {}, crear("span", {}, ejercicio.nombre ?? nombreDeEjercicio(ejercicio.ejercicio_id) ?? "Ejercicio"), detalle ? crear("span", { className: "nota-suave" }, ` ${detalle}`) : null);
}

function dibujarSesiones(sesiones, programa) {
  const nombres = new Map((programa?.sesiones_planificadas ?? []).map((sesion) => [sesion.id, sesion.nombre]));
  const ultimas = [...sesiones].sort((a, b) => b.creada_en.localeCompare(a.creada_en)).slice(0, 5);
  $("[data-sesiones]").replaceChildren(ultimas.length
    ? crear("ul", { className: "sesiones-hechas" }, ultimas.map((sesion) => {
      const prescripcion = sesion.prescripcion_efectiva;
      const razones = (prescripcion?.explicacion ?? []).map((razon) => razon.datos?.explicacion).filter(Boolean);
      return crear("li", {},
        crear("p", { className: "aviso-titulo" },
          crear("strong", {}, nombres.get(sesion.sesion_planificada_id) ?? "Sesión de una versión anterior"),
          crear("span", { className: "nota-suave" }, fechaLegible(sesion.creada_en))),
        prescripcion?.ejercicios?.length ? crear("ul", { className: "prescripcion" }, prescripcion.ejercicios.map(renglonPrescripcion)) : null,
        razones.map((razon) => crear("p", { className: "nota-suave" }, razon)));
    }))
    : crear("p", { className: "nota-suave" }, "Todavía no registró sesiones."));
}

function dibujarSalud(vista) {
  const contenedor = $("[data-salud]");
  if (vista.sin_consentimiento) {
    contenedor.replaceChildren(crear("p", { className: "nota-suave" }, "El socio no dio consentimiento para mostrar sus datos de salud."));
    return;
  }
  const { dolores_reportados: dolores, restricciones_salud: restricciones } = vista.salud;
  const filas = [
    ...restricciones.map((restriccion) => crear("li", {},
      crear("strong", {}, "Restricción"), ` ${restriccion.descripcion ?? ""}`,
      crear("span", { className: "nota-suave" }, [restriccion.zona && nombreDeZona(restriccion.zona), restriccion.patron_movimiento, nombreDeEjercicio(restriccion.ejercicio_id)].filter(Boolean).join(" · ")))),
    ...dolores.map((dolor) => crear("li", {},
      crear("strong", {}, "Dolor"), ` ${nombreDeZona(dolor.zona)}`,
      crear("span", { className: "nota-suave" }, dolor.creado_en ? fechaLegible(dolor.creado_en) : ""))),
  ];
  contenedor.replaceChildren(filas.length
    ? crear("ul", { className: "salud-lista" }, filas)
    : crear("p", { className: "nota-suave" }, "Sin dolores reportados ni restricciones vigentes."));
}

function dibujarSocio(vista) {
  const { socio } = vista;
  $("[data-socio-nombre]").textContent = `${socio.nombre} ${socio.apellido}`;
  $("[data-socio-programa]").textContent = vista.programa_vigente ? "" : "Sin programa";
  $("[data-socio-programa]").hidden = Boolean(vista.programa_vigente);
  $("[data-abrir-editor]").href = `/editor-programa.html?socio=${socio.id}`;
  const perfil = $("[data-perfil]");
  if (perfil.dataset.perfilSocio !== socio.id) {
    perfil.dataset.perfilSocio = socio.id;
    montarPerfil(perfil, `/api/socios/${socio.id}/perfil`);
  }
  const sinRevisar = avisosSinRevisar(vista.avisos);
  // Lo que se revisa es exactamente lo que esta pantalla mostró: un aviso posterior no queda revisado sin verse.
  avisosALaVista = sinRevisar.map((aviso) => aviso.id);
  $("[data-revision]").hidden = sinRevisar.length === 0;
  $("[data-avisos-sin-revisar]").replaceChildren(...sinRevisar.map(renglonAviso));
  $("[data-revisar]").textContent = sinRevisar.length === 1 ? "Marcar como revisado" : `Marcar los ${sinRevisar.length} como revisados`;
  const revisados = vista.avisos.filter((aviso) => aviso.revisado);
  $("[data-historial]").hidden = revisados.length === 0;
  $("[data-avisos-revisados]").replaceChildren(...revisados.map(renglonAviso));
  dibujarPrograma(vista.programa_vigente);
  dibujarSesiones(vista.sesiones_realizadas, vista.programa_vigente);
  dibujarSalud(vista);
}

async function leerSocio(id) {
  const lectura = ++lecturaDeSocio;
  try {
    const vista = await llamarApi(`/api/entrenador/socios/${id}`);
    if (lectura !== lecturaDeSocio || id !== socioAbierto) return;
    $("[data-socio]").hidden = false;
    $("[data-socio-error]").textContent = "";
    dibujarSocio(vista);
  } catch (error) {
    // La hoja sigue oculta si este socio no llegó a dibujarse: no quedan a la vista los datos del anterior.
    if (lectura === lecturaDeSocio && id === socioAbierto) $("[data-socio-error]").textContent = error.message;
  }
}

function mostrarSocio(id, { enfocar = false } = {}) {
  if (id !== socioAbierto) {
    if (control.actual && !control.enCurso) control.descartar();
    $("[data-nota]").value = "";
    $("[data-error-revision]").textContent = "";
    $("[data-socio-error]").textContent = "";
    $("[data-socio]").hidden = true;
  }
  socioAbierto = id;
  $("[data-bandeja]").dataset.abierto = String(Boolean(id));
  $("[data-indicacion]").hidden = Boolean(id);
  if (!id) $("[data-socio]").hidden = true;
  if (gruposActuales) dibujarGrupos(gruposActuales);
  if (!id) return;
  const lectura = leerSocio(id);
  if (enfocar) lectura.then(() => $("[data-hoja]").focus({ preventScroll: false }));
}

async function revisar(evento) {
  evento.preventDefault();
  const boton = $("[data-revisar]");
  const nota = $("[data-nota]").value.trim();
  control.preparar(`/api/entrenador/socios/${socioAbierto}/avisos/revision`, { aviso_ids: avisosALaVista, nota: nota || null });
  const operacion = control.comenzar();
  if (!operacion) return;
  boton.disabled = true;
  $("[data-error-revision]").textContent = "";
  try {
    await llamarApi(operacion.ruta, { metodo: "POST", cuerpo: operacion.cuerpo, clave: operacion.clave });
    control.finalizar();
    $("[data-nota]").value = "";
    $("[data-estado]").textContent = "Avisos revisados.";
    sondeo.invalidar();
    sondeo.actualizar();
    await leerSocio(socioAbierto);
    $("[data-hoja]").focus({ preventScroll: true });
  } catch (error) {
    control.finalizar(error);
    $("[data-error-revision]").textContent = control.actual
      ? `${error.message} Podés reintentar: la revisión no se va a duplicar.`
      : error.message;
  } finally {
    boton.disabled = false;
  }
}

function prepararNavegacion() {
  document.addEventListener("click", (evento) => {
    const verGrupo = evento.target.closest("[data-ver-grupo]");
    if (verGrupo) {
      const tipo = verGrupo.dataset.verGrupo;
      if (gruposAbiertos.has(tipo)) gruposAbiertos.delete(tipo);
      else gruposAbiertos.add(tipo);
      dibujarGrupos(gruposActuales);
      return;
    }
    const enlace = evento.target.closest("[data-enlace-socio], [data-volver]");
    if (!enlace || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.button !== 0) return;
    evento.preventDefault();
    history.pushState(null, "", enlace.href);
    mostrarSocio(enlace.dataset.enlaceSocio ?? null, { enfocar: Boolean(enlace.dataset.enlaceSocio) });
  });
  addEventListener("popstate", () => mostrarSocio(pagina().searchParams.get("socio")));
}

async function iniciar() {
  const usuario = await exigirRol(["entrenador"]);
  if (!usuario) return;
  prepararBarra(usuario);
  prepararNavegacion();
  $("[data-formulario-revision]").addEventListener("submit", revisar);
  try {
    catalogo = new Map((await llamarApi("/api/ejercicios")).ejercicios.map((ejercicio) => [ejercicio.id, ejercicio]));
  } catch { /* Sin catálogo los avisos se leen igual, sin el nombre del ejercicio. */ }
  mostrarSocio(pagina().searchParams.get("socio"));
  sondeo = crearSondeo({
    url: "/api/entrenador/bandeja",
    alCambiar(datos) {
      if ($("[data-estado]").textContent === "Cargando la bandeja…") $("[data-estado]").textContent = "";
      alCambiarBandeja(datos);
    },
    alFallar() {
      if (!gruposActuales) $("[data-error]").textContent = "No se pudo cargar la bandeja. Se reintenta solo.";
    },
  });
}

iniciar().catch((error) => {
  $("[data-error]").textContent = error.message;
  $("[data-estado]").textContent = "";
});
