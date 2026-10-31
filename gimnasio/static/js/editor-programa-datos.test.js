import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ajustarSeries, conservarFormulario, cuerpoDePublicacion, cuerpoDePlantilla, fijarCargaPartida, filaNueva, idsDeEjercicios, leerFormulario, olvidarFormulario,
  problemasDeLaSemana, semanaDesdePlantilla, semanaDesdeVigente, sesionesGeneradas, sustituirEjercicio,
} from "./editor-programa-datos.js";

const sentadilla = { id: "s", nombre: "Sentadilla", medidas_aplicables: ["repeticiones", "carga"] };
const caminata = { id: "c", nombre: "Caminata", medidas_aplicables: ["duracion", "distancia"] };
const catalogo = new Map([[sentadilla.id, sentadilla], [caminata.id, caminata]]);

const semana = () => ({
  semanas: "8",
  sesiones: [{ nombre: " Fuerza ", ejercicios: [filaNueva(sentadilla), filaNueva(caminata)] }],
});

test("el modo plantilla no exige duración ni carga y no las envía", () => {
  const datos = semana();
  datos.semanas = "";
  assert.deepEqual(problemasDeLaSemana(datos, catalogo, {}, true), []);
  const cuerpo = cuerpoDePlantilla(datos, " Fuerza ", " Descripción ", catalogo);
  assert.equal(cuerpo.nombre, "Fuerza");
  assert.equal(cuerpo.descripcion, "Descripción");
  assert.equal("semanas" in cuerpo, false);
  for (const ejercicio of cuerpo.sesiones[0].ejercicios) {
    assert.equal("carga" in ejercicio, false);
    assert.equal("carga_partida" in ejercicio, false);
  }
});

test("publicar identifica solo la plantilla elegida, nunca la de una versión vigente", () => {
  assert.equal(cuerpoDePublicacion(semana(), null, catalogo, "plantilla:ejemplo").plantilla_id, "ejemplo");
  assert.equal("plantilla_id" in cuerpoDePublicacion(semana(), 2, catalogo, "vigente"), false);
});

test("un ejercicio nuevo solo trae los campos de sus medidas", () => {
  assert.equal(filaNueva(sentadilla).repeticiones_minimas, "8");
  assert.equal(filaNueva(sentadilla).duracion, "");
  assert.equal(filaNueva(caminata).duracion, "600");
  assert.equal(filaNueva(caminata).repeticiones_minimas, "");
});

test("partir de la versión vigente conserva la semana pero no su carga de partida", () => {
  const nueva = semanaDesdeVigente({
    duracion_semanas: 6,
    sesiones: [{ nombre: "Fuerza", ejercicios: [{ ejercicio_id: "s", series: 4, carga: "20.50", carga_partida: "18.00", repeticiones_minimas: 8, repeticiones_maximas: 12 }] }],
  });
  assert.equal(nueva.semanas, "6");
  assert.equal(nueva.sesiones[0].ejercicios[0].series, "4");
  assert.equal(nueva.sesiones[0].ejercicios[0].carga, "20.50");
  assert.equal(nueva.sesiones[0].ejercicios[0].carga_partida, "");
});

test("un programa anterior sin semanas parte de la duración por defecto", () => {
  assert.equal(semanaDesdeVigente({ duracion_semanas: null, sesiones: [] }).semanas, "8");
});

test("una plantilla arranca con 8 semanas", () => {
  const nueva = semanaDesdePlantilla({ sesiones: [{ nombre: "Fuerza 1", ejercicios: [{ ejercicio_id: "s", series: 3, repeticiones_minimas: 8, repeticiones_maximas: 12, rir_objetivo: 2, descanso: 90 }] }] });
  assert.equal(nueva.semanas, "8");
  assert.equal(sesionesGeneradas(nueva), 8);
});

test("las series quedan entre 1 y 10", () => {
  assert.equal(ajustarSeries("3", 1), "4");
  assert.equal(ajustarSeries("10", 1), "10");
  assert.equal(ajustarSeries("1", -1), "1");
  assert.equal(ajustarSeries("", 1), "1");
});

test("la carga de partida es una sola por ejercicio en la versión", () => {
  const actual = { semanas: "8", sesiones: [{ nombre: "A", ejercicios: [filaNueva(sentadilla)] }, { nombre: "B", ejercicios: [filaNueva(sentadilla)] }] };
  fijarCargaPartida(actual, "s", "30");
  assert.deepEqual(actual.sesiones.map((sesion) => sesion.ejercicios[0].carga_partida), ["30", "30"]);
  assert.deepEqual(idsDeEjercicios(actual), ["s"]);
});

test("sustituir por una alternativa conserva las series", () => {
  const actual = semana();
  actual.sesiones[0].ejercicios[0].series = "5";
  sustituirEjercicio(actual, "s", { ...sentadilla, id: "m" });
  assert.equal(actual.sesiones[0].ejercicios[0].ejercicio_id, "m");
  assert.equal(actual.sesiones[0].ejercicios[0].series, "5");
});

test("explica los límites antes de enviar", () => {
  assert.deepEqual(problemasDeLaSemana({ semanas: "3", sesiones: [] }, catalogo), ["La duración va de 4 a 12 semanas.", "Agregá al menos una sesión."]);
  const conProblemas = semana();
  conProblemas.sesiones[0].ejercicios[0].series = "11";
  conProblemas.sesiones[0].ejercicios[0].repeticiones_minimas = "15";
  assert.deepEqual(problemasDeLaSemana(conProblemas, catalogo), [
    "Sentadilla: las series van de 1 a 10.",
    "Sentadilla: el mínimo de repeticiones no puede superar el máximo.",
    "Sentadilla: no tiene historial; fijá una carga de partida.",
  ]);
  assert.deepEqual(problemasDeLaSemana({ semanas: "8", sesiones: [{ nombre: "", ejercicios: [] }] }, catalogo), ["La sesión 1 necesita un nombre.", "La sesión 1 no tiene ejercicios."]);
});

test("con carga sugerida no exige carga de partida", () => {
  assert.deepEqual(problemasDeLaSemana(semana(), catalogo, { s: "20.00" }), []);
});

test("el cuerpo no manda campos ajenos a las medidas del ejercicio", () => {
  const actual = semana();
  actual.sesiones[0].ejercicios[0].carga_partida = "22.5";
  const cuerpo = cuerpoDePublicacion(actual, 3, catalogo);
  assert.equal(cuerpo.version_base, 3);
  assert.equal(cuerpo.semanas, 8);
  assert.equal(cuerpo.sesiones[0].nombre, "Fuerza");
  const [fuerza, marcha] = cuerpo.sesiones[0].ejercicios;
  assert.equal(fuerza.series, 3);
  assert.equal(fuerza.carga_partida, "22.5");
  assert.equal(fuerza.carga, null);
  assert.equal("duracion" in fuerza, false);
  assert.equal("carga" in marcha, false);
  assert.equal("repeticiones_minimas" in marcha, false);
  assert.equal(marcha.duracion, 600);
  assert.equal(marcha.distancia, "1000");
});

test("el formulario se conserva por socio y un almacenamiento roto no molesta", () => {
  const datos = new Map();
  const almacen = { getItem: (clave) => datos.get(clave) ?? null, setItem: (clave, valor) => datos.set(clave, valor), removeItem: (clave) => datos.delete(clave) };
  conservarFormulario(almacen, "s1", { semana: semana() });
  assert.equal(leerFormulario(almacen, "s1").semana.semanas, "8");
  assert.equal(leerFormulario(almacen, "s2"), null);
  olvidarFormulario(almacen, "s1");
  assert.equal(leerFormulario(almacen, "s1"), null);
  const roto = { getItem() { throw new Error("bloqueado"); }, setItem() { throw new Error("bloqueado"); }, removeItem() { throw new Error("bloqueado"); } };
  assert.equal(leerFormulario(roto, "s1"), null);
  conservarFormulario(roto, "s1", {});
  olvidarFormulario(roto, "s1");
});
