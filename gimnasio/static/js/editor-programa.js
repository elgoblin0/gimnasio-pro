import { llamarApi } from "@comun/api.js";
import { formatearCarga } from "@comun/formatos.js";
import { crear, exigirRol, prepararBarra } from "@comun/personal.js";
import { registrarPwa } from "@comun/pwa.js";
import { calcularVolumenPorZona, totalDeSeries } from "@comun/volumen-zonas.js";
import { crearVolumenZonas, ZONAS_CUERPO } from "@comun/zonas.js";
import {
  ajustarSeries, campoAplica, conservarFormulario, cuerpoDePublicacion, fijarCargaPartida, filaNueva, idsDeEjercicios, leerFormulario, olvidarFormulario,
  problemasDeLaSemana, semanaDesdePlantilla, semanaDesdeVigente, semanaVacia, sesionesGeneradas, sustituirEjercicio,
} from "./editor-programa-datos.js";
import { nombreDeEquipo } from "./equipos-datos.js";

registrarPwa();

const $ = (selector) => document.querySelector(selector);
const socioId = new URL(location.href).searchParams.get("socio");
const nombreDeZona = (id) => ZONAS_CUERPO.find((zona) => zona.id === id)?.nombre ?? id;

let socio = null;
let catalogo = new Map();
let plantillas = [];
let vigente = null;
let versionBase = null;
let semana = semanaVacia();
let origen = null;
let anterior = null;
let sugeridas = {};
let choques = new Map();
let cuerpo = null;
let envio = null;

function guardar() {
  conservarFormulario(localStorage, socioId, { semana, versionBase, origen });
}

function actualizarCuerpo() {
  const zonas = (id) => catalogo.get(id)?.zonas ?? [];
  cuerpo?.actualizar(calcularVolumenPorZona(semana.sesiones, zonas), totalDeSeries(semana.sesiones));
}

function actualizarPie() {
  const generadas = sesionesGeneradas(semana);
  $("[data-generadas]").textContent = semana.sesiones.length
    ? `${semana.sesiones.length} ${semana.sesiones.length === 1 ? "sesión" : "sesiones"} por semana · ${generadas} en total`
    : "";
  $("[data-publicar]").textContent = `Publicar versión ${(vigente?.version ?? 0) + 1}`;
}

function alCambiarNumeros() {
  actualizarCuerpo();
  actualizarPie();
  guardar();
}

function campoNumero(s, e, ejercicio, campo, etiqueta, atributos) {
  return crear("label", { className: `campo-corto campo-${campo}` }, etiqueta,
    crear("input", { type: "number", inputMode: "decimal", value: ejercicio[campo], "data-s": s, "data-e": e, "data-campo": campo, ...atributos }));
}

function ayudaDeCarga(ejercicio) {
  const sugerida = sugeridas[ejercicio.ejercicio_id];
  if (sugerida) return `El motor propondría hoy ${formatearCarga(sugerida)}. Una carga mayor no se aplica.`;
  if (ejercicio.carga) return `Carga del programa: ${formatearCarga(ejercicio.carga)}.`;
  return "Sin historial: fijá la carga inicial.";
}

function filaDeEjercicio(ejercicio, s, e) {
  const datos = catalogo.get(ejercicio.ejercicio_id);
  const nombre = datos?.nombre ?? "Ejercicio";
  const choque = choques.get(ejercicio.ejercicio_id);
  const campos = [];
  if (campoAplica("repeticiones_minimas", datos)) {
    campos.push(
      campoNumero(s, e, ejercicio, "repeticiones_minimas", "Rep. mín.", { min: 1, step: 1 }),
      campoNumero(s, e, ejercicio, "repeticiones_maximas", "Rep. máx.", { min: 1, step: 1 }),
    );
  }
  if (campoAplica("duracion", datos)) campos.push(campoNumero(s, e, ejercicio, "duracion", "Duración (s)", { min: 1, step: 1 }));
  if (campoAplica("distancia", datos)) campos.push(campoNumero(s, e, ejercicio, "distancia", "Distancia (m)", { min: 0.01, step: "any" }));
  campos.push(
    campoNumero(s, e, ejercicio, "rir_objetivo", "RIR", { min: 0, max: 5, step: 1 }),
    campoNumero(s, e, ejercicio, "descanso", "Descanso (s)", { min: 0, step: 5 }),
  );
  if (campoAplica("carga", datos)) campos.push(campoNumero(s, e, ejercicio, "carga_partida", "Carga de partida (kg)", { min: 0, step: "any" }));
  return crear("li", { className: "fila-plan", "data-fila-ejercicio": ejercicio.ejercicio_id, "data-choque": choque ? "true" : undefined },
    crear("div", { className: "plan-titulo" },
      crear("p", { className: "plan-nombre" }, nombre),
      crear("p", { className: "nota-suave" }, [
        datos?.equipo && nombreDeEquipo(datos.equipo),
        datos?.estado_equipo === "fuera_de_servicio" ? "fuera de servicio" : null,
        (datos?.zonas ?? []).map(nombreDeZona).join(", "),
      ].filter(Boolean).join(" · "))),
    crear("div", { className: "plan-series", role: "group", "aria-label": `Series de ${nombre}` },
      crear("button", { type: "button", className: "boton-icono", "data-series": -1, "data-s": s, "data-e": e, "aria-label": `Una serie menos en ${nombre}` }, "−"),
      crear("label", {}, crear("span", { className: "solo-lector" }, `Series de ${nombre}`),
        crear("input", { type: "number", inputMode: "numeric", min: 1, max: 10, step: 1, value: ejercicio.series, "data-s": s, "data-e": e, "data-campo": "series" })),
      crear("button", { type: "button", className: "boton-icono", "data-series": 1, "data-s": s, "data-e": e, "aria-label": `Una serie más en ${nombre}` }, "+"),
      crear("span", { className: "plan-unidad", "aria-hidden": "true" }, "series")),
    crear("div", { className: "plan-campos" }, campos),
    crear("button", { type: "button", className: "boton-icono plan-quitar", "data-quitar-ejercicio": true, "data-s": s, "data-e": e, "aria-label": `Quitar ${nombre}` }, "×"),
    campoAplica("carga", datos) ? crear("p", { className: "nota-suave plan-ayuda", "data-ayuda-carga": ejercicio.ejercicio_id }, ayudaDeCarga(ejercicio)) : null,
    choque
      ? crear("div", { className: "plan-choque" },
        crear("p", {}, choque.mensaje),
        crear("div", { className: "editor-acciones" }, choque.alternativas.length
          ? choque.alternativas.map((alternativa) => crear("button", { type: "button", className: "boton-borde", "data-usar-alternativa": alternativa.ejercicio_id, "data-reemplaza": ejercicio.ejercicio_id }, `Usar ${alternativa.nombre}`))
          : crear("p", { className: "nota-suave" }, "No tiene alternativas disponibles: quitalo o elegí otro ejercicio.")))
      : null);
}

function bloqueDeSesion(sesion, s) {
  const idSelect = `agregar-ejercicio-${s}`;
  const presentes = new Set(sesion.ejercicios.map((ejercicio) => ejercicio.ejercicio_id));
  return crear("section", { className: "sesion-plan", "data-sesion": s, "aria-label": `Sesión ${s + 1}` },
    crear("div", { className: "sesion-cabecera" },
      crear("span", { className: "sesion-numero", "aria-hidden": "true" }, String(s + 1)),
      crear("label", { className: "sesion-nombre" },
        crear("span", { className: "solo-lector" }, `Nombre de la sesión ${s + 1}`),
        crear("input", { value: sesion.nombre, maxLength: 108, "data-s": s, "data-nombre-sesion": true, placeholder: "Nombre de la sesión" })),
      crear("button", { type: "button", className: "boton-enlace", "data-quitar-sesion": s, "aria-label": `Quitar la sesión ${s + 1}` }, "Quitar")),
    crear("ul", { className: "filas-plan" }, sesion.ejercicios.map((ejercicio, e) => filaDeEjercicio(ejercicio, s, e))),
    crear("div", { className: "agregar-ejercicio" },
      crear("label", { htmlFor: idSelect, className: "solo-lector" }, `Agregar ejercicio a la sesión ${s + 1}`),
      crear("select", { id: idSelect, "data-agregar-ejercicio": s },
        crear("option", { value: "" }, "Agregar ejercicio…"),
        [...catalogo.values()].filter((ejercicio) => !presentes.has(ejercicio.id)).map((ejercicio) => crear("option", { value: ejercicio.id },
          ejercicio.estado_equipo === "fuera_de_servicio" ? `${ejercicio.nombre} (equipo fuera de servicio)` : ejercicio.nombre)))));
}

function dibujarOrigenes() {
  const opciones = [
    ...(vigente ? [{ clave: "vigente", texto: `Versión vigente ${vigente.version}`, detalle: `${vigente.sesiones.length} ${vigente.sesiones.length === 1 ? "sesión" : "sesiones"} por semana` }] : []),
    ...plantillas.map((plantilla) => ({ clave: `plantilla:${plantilla.id}`, texto: plantilla.nombre, detalle: `${plantilla.sesiones.length} ${plantilla.sesiones.length === 1 ? "sesión" : "sesiones"} por semana` })),
  ];
  $("[data-origenes]").replaceChildren(...opciones.map(({ clave, texto, detalle }) => crear("button", {
    type: "button", className: "origen", "data-origen": clave, "aria-pressed": String(clave === origen),
  }, crear("span", {}, texto), crear("span", { className: "nota-suave" }, detalle))));
}

function dibujarSemana() {
  $("[data-sesiones]").replaceChildren(...semana.sesiones.map(bloqueDeSesion));
  $("[data-sin-sesiones]").hidden = semana.sesiones.length > 0;
  $("[data-agregar-sesion]").disabled = semana.sesiones.length >= 6;
  $("[data-duracion]").value = semana.semanas;
  dibujarOrigenes();
  alCambiarNumeros();
}

async function pedirSugeridas() {
  const faltan = idsDeEjercicios(semana).filter((id) => !(id in sugeridas));
  if (!faltan.length) return;
  try {
    const { cargas } = await llamarApi(`/api/socios/${socioId}/programa/cargas-sugeridas?ejercicios=${faltan.join(",")}`);
    Object.assign(sugeridas, cargas);
    for (const ayuda of document.querySelectorAll("[data-ayuda-carga]")) {
      const ejercicio = semana.sesiones.flatMap((sesion) => sesion.ejercicios).find((fila) => fila.ejercicio_id === ayuda.dataset.ayudaCarga);
      if (ejercicio) ayuda.textContent = ayudaDeCarga(ejercicio);
    }
  } catch { /* La sugerencia informa: sin ella se puede seguir editando. */ }
}

function reemplazarSemana(nueva, claveOrigen, { base = versionBase } = {}) {
  anterior = semana.sesiones.length ? { semana, origen, versionBase } : null;
  semana = nueva;
  origen = claveOrigen;
  versionBase = base;
  choques = new Map();
  $("[data-deshacer]").hidden = !anterior;
  $("[data-recuperado]").hidden = true;
  $("[data-problemas]").replaceChildren();
  dibujarSemana();
  pedirSugeridas();
}

function elegirOrigen(clave) {
  if (clave === "vigente") reemplazarSemana(semanaDesdeVigente(vigente), clave, { base: vigente.version });
  else reemplazarSemana(semanaDesdePlantilla(plantillas.find((plantilla) => `plantilla:${plantilla.id}` === clave)), clave, { base: vigente?.version ?? null });
}

function posicion(nodo) {
  return { s: Number(nodo.dataset.s), e: Number(nodo.dataset.e) };
}

function prepararEventos() {
  const formulario = $("[data-formulario]");
  formulario.addEventListener("input", (evento) => {
    const nodo = evento.target;
    if (nodo.dataset.duracion !== undefined) semana.semanas = nodo.value;
    else if (nodo.dataset.nombreSesion !== undefined) semana.sesiones[Number(nodo.dataset.s)].nombre = nodo.value;
    else if (nodo.dataset.campo) {
      const { s, e } = posicion(nodo);
      const ejercicio = semana.sesiones[s].ejercicios[e];
      ejercicio[nodo.dataset.campo] = nodo.value;
      if (nodo.dataset.campo === "carga_partida") {
        fijarCargaPartida(semana, ejercicio.ejercicio_id, nodo.value);
        for (const otro of formulario.querySelectorAll(`[data-fila-ejercicio="${ejercicio.ejercicio_id}"] [data-campo="carga_partida"]`)) {
          if (otro !== nodo) otro.value = nodo.value;
        }
      }
    } else return;
    alCambiarNumeros();
  });
  formulario.addEventListener("change", (evento) => {
    const s = evento.target.dataset.agregarEjercicio;
    if (s === undefined || !evento.target.value) return;
    semana.sesiones[Number(s)].ejercicios.push(filaNueva(catalogo.get(evento.target.value)));
    const indice = semana.sesiones[Number(s)].ejercicios.length - 1;
    dibujarSemana();
    pedirSugeridas();
    $(`[data-sesion="${s}"] .fila-plan:nth-child(${indice + 1}) [data-campo="series"]`)?.focus();
  });
  formulario.addEventListener("click", (evento) => {
    const boton = evento.target.closest("button");
    if (!boton) return;
    if (boton.dataset.series) {
      const { s, e } = posicion(boton);
      const ejercicio = semana.sesiones[s].ejercicios[e];
      ejercicio.series = ajustarSeries(ejercicio.series, Number(boton.dataset.series));
      boton.parentElement.querySelector("input").value = ejercicio.series;
      alCambiarNumeros();
    } else if (boton.dataset.quitarEjercicio) {
      const { s, e } = posicion(boton);
      const [quitado] = semana.sesiones[s].ejercicios.splice(e, 1);
      choques.delete(quitado.ejercicio_id);
      dibujarSemana();
      ($(`[data-sesion="${s}"] .fila-plan:nth-child(${e + 1}) .plan-quitar`) ?? $(`[data-agregar-ejercicio="${s}"]`))?.focus();
    } else if (boton.dataset.quitarSesion !== undefined) {
      semana.sesiones.splice(Number(boton.dataset.quitarSesion), 1);
      dibujarSemana();
      $("[data-agregar-sesion]").focus();
    } else if (boton.dataset.origen) {
      elegirOrigen(boton.dataset.origen);
      $(`[data-origen="${boton.dataset.origen}"]`)?.focus();
    } else if (boton.dataset.usarAlternativa) {
      sustituirEjercicio(semana, boton.dataset.reemplaza, catalogo.get(boton.dataset.usarAlternativa));
      choques.delete(boton.dataset.reemplaza);
      dibujarSemana();
      pedirSugeridas();
    }
  });
  $("[data-agregar-sesion]").addEventListener("click", () => {
    semana.sesiones.push({ nombre: `Sesión ${semana.sesiones.length + 1}`, ejercicios: [] });
    dibujarSemana();
    $(`[data-sesion="${semana.sesiones.length - 1}"] [data-nombre-sesion]`)?.focus();
  });
  $("[data-deshacer-boton]").addEventListener("click", () => {
    if (!anterior) return;
    ({ semana, origen, versionBase } = anterior);
    anterior = null;
    $("[data-deshacer]").hidden = true;
    dibujarSemana();
    pedirSugeridas();
    $("[data-agregar-sesion]").focus();
  });
  formulario.addEventListener("submit", publicar);
  $("[data-conflicto-mantener]").addEventListener("click", () => {
    versionBase = vigente?.version ?? null;
    $("[data-conflicto]").hidden = true;
    dibujarOrigenes();
    alCambiarNumeros();
    $("[data-publicar]").focus();
  });
  $("[data-conflicto-cargar]").addEventListener("click", () => {
    $("[data-conflicto]").hidden = true;
    anterior = null;
    reemplazarSemana(semanaDesdeVigente(vigente), "vigente", { base: vigente.version });
    $("[data-agregar-sesion]").focus();
  });
}

async function mostrarConflicto() {
  const { programa } = await llamarApi(`/api/socios/${socioId}/programa`);
  vigente = programa;
  const version = vigente?.version;
  $("[data-conflicto-texto]").textContent = version
    ? `Otra persona publicó la versión ${version} mientras editabas. Tu semana sigue acá: decidí si la mantenés sobre esa versión o cargás la nueva.`
    : "La versión de base ya no existe. Tu semana sigue acá.";
  $("[data-conflicto-cargar]").hidden = !version;
  $("[data-conflicto]").hidden = false;
  dibujarOrigenes();
  actualizarPie();
  $("[data-conflicto]").scrollIntoView({ block: "center" });
  $("[data-conflicto-mantener]").focus();
}

function mostrarProblemas(problemas) {
  $("[data-problemas]").replaceChildren(...problemas.map((problema) => crear("li", {}, problema)));
}

function mostrarPublicado(programa) {
  olvidarFormulario(localStorage, socioId);
  $("[data-editor]").hidden = true;
  $("[data-publicado]").hidden = false;
  $("[data-publicado-titulo]").textContent = `Publicaste la versión ${programa.version}`;
  $("[data-publicado-texto]").textContent = `${socio.nombre} la recibe en su próxima sesión. Una sesión en curso no cambia y su progresión sigue con su historial.`;
  $("[data-publicado-enlace]").href = `/bandeja.html?socio=${socioId}`;
  $("[data-publicado]").focus();
}

async function publicar(evento) {
  evento.preventDefault();
  const problemas = problemasDeLaSemana(semana, catalogo, sugeridas);
  mostrarProblemas(problemas);
  if (problemas.length) return;
  const cuerpoEnvio = cuerpoDePublicacion(semana, versionBase, catalogo);
  const huella = JSON.stringify(cuerpoEnvio);
  // Si se cortó la red, reintentar lo mismo no publica dos versiones.
  if (envio?.huella !== huella) envio = { huella, clave: crypto.randomUUID() };
  const boton = $("[data-publicar]");
  boton.disabled = true;
  $("[data-estado]").textContent = "Publicando…";
  try {
    const { programa } = await llamarApi(`/api/socios/${socioId}/programas`, { metodo: "POST", cuerpo: cuerpoEnvio, clave: envio.clave });
    envio = null;
    $("[data-estado]").textContent = "";
    mostrarPublicado(programa);
  } catch (error) {
    $("[data-estado]").textContent = "";
    if (error.estadoHttp !== 0 && error.estadoHttp < 500) envio = null;
    if (error.codigo === "version_desactualizada") {
      await mostrarConflicto();
    } else if (error.codigo === "choque_restriccion") {
      choques = new Map((error.detalles?.choques ?? []).map((choque) => [choque.ejercicio_id, choque]));
      dibujarSemana();
      mostrarProblemas([`${choques.size === 1 ? "Un ejercicio choca" : `${choques.size} ejercicios chocan`} con una restricción de salud vigente. Corregilo para publicar.`]);
      $("[data-choque] button")?.focus();
    } else if (error.estadoHttp === 0) {
      mostrarProblemas(["Se cortó la conexión. Tu formulario quedó guardado en este navegador; podés volver a publicar."]);
    } else {
      mostrarProblemas([error.message]);
    }
  } finally {
    boton.disabled = false;
  }
}

function dibujarCabecera(vista) {
  $("[data-titulo]").textContent = `Programa de ${socio.nombre} ${socio.apellido}`;
  $("[data-volver-socio]").href = `/bandeja.html?socio=${socioId}`;
  document.title = `${socio.nombre} ${socio.apellido} · Editor · Gimnasio Pro`;
  const restricciones = vista.salud?.restricciones_salud ?? [];
  if (restricciones.length) {
    $("[data-restricciones]").hidden = false;
    $("[data-restricciones]").textContent = `Restricciones vigentes: ${restricciones.map((restriccion) => [restriccion.descripcion, restriccion.zona && nombreDeZona(restriccion.zona), restriccion.patron_movimiento].filter(Boolean)[0]).join(" · ")}`;
  }
  $("[data-base]").textContent = vigente ? `Versión vigente: ${vigente.version}` : "Todavía no tiene programa.";
}

async function iniciar() {
  const usuario = await exigirRol(["entrenador"]);
  if (!usuario) return;
  prepararBarra(usuario);
  if (!socioId) throw new Error("Abrí el editor desde la bandeja, eligiendo un socio.");
  const [vista, respuestaPlantillas, respuestaEjercicios, respuestaPrograma] = await Promise.all([
    llamarApi(`/api/entrenador/socios/${socioId}`),
    llamarApi("/api/programas/plantillas"),
    llamarApi("/api/ejercicios"),
    llamarApi(`/api/socios/${socioId}/programa`),
  ]);
  socio = vista.socio;
  catalogo = new Map(respuestaEjercicios.ejercicios.sort((a, b) => a.nombre.localeCompare(b.nombre, "es")).map((ejercicio) => [ejercicio.id, ejercicio]));
  plantillas = respuestaPlantillas.plantillas.sort((a, b) => a.sesiones.length - b.sesiones.length);
  vigente = respuestaPrograma.programa;
  versionBase = vigente?.version ?? null;
  dibujarCabecera(vista);
  prepararEventos();
  cuerpo = crearVolumenZonas($("[data-volumen]"), vista.figura_cuerpo);

  const conservado = leerFormulario(localStorage, socioId);
  if (conservado) {
    ({ semana, origen, versionBase } = conservado);
    $("[data-recuperado]").hidden = false;
    $("[data-recuperado]").textContent = "Recuperamos el formulario que no llegaste a publicar.";
  } else if (vigente) {
    semana = semanaDesdeVigente(vigente);
    origen = "vigente";
  }
  $("[data-editor]").hidden = false;
  $("[data-estado]").textContent = "";
  dibujarSemana();
  // Abrir el editor no es editar: sin cambios no hay formulario que recuperar la próxima vez.
  if (!conservado) olvidarFormulario(localStorage, socioId);
  pedirSugeridas();
  if (conservado && versionBase !== (vigente?.version ?? null)) await mostrarConflicto();
}

iniciar().catch((error) => {
  $("[data-estado]").textContent = "";
  $("[data-error]").textContent = error.message;
});
