import assert from "node:assert/strict";
import { test } from "node:test";

import { describirObjetivos, mensajeDeOperacion, razonesVisibles, seQuito, sinTrabajoHoy } from "./entrenamiento-textos.js";

const objetivos = { series: 2, repeticiones_minimas: 8, repeticiones_maximas: 12, carga: "23.00", duracion: null, distancia: null };

test("los objetivos no repiten un rango de un solo valor", () => {
  assert.equal(describirObjetivos(objetivos), "2 series · 8–12 reps · 23,00 kg");
  assert.equal(describirObjetivos({ ...objetivos, series: 1, repeticiones_minimas: 12 }), "1 serie · 12 reps · 23,00 kg");
});

test("la duración exacta en minutos se lee en minutos", () => {
  const cardio = { series: 1, carga: null, duracion: 1200, distancia: "1500" };
  assert.equal(describirObjetivos(cardio), "1 serie · 20 min · 1.500 m");
  assert.equal(describirObjetivos({ ...cardio, duracion: 45 }), "1 serie · 45 s · 1.500 m");
  assert.equal(describirObjetivos({ ...cardio, duracion: 90 }), "1 serie · 90 s · 1.500 m");
});

test("sin ejercicios para hacer hoy solo si ninguno se puede hacer", () => {
  const quitado = { objetivos: { series: 0 }, no_disponible: false };
  const disponible = { objetivos: { series: 2 }, no_disponible: false };
  const sinEquipo = { objetivos: { series: 2 }, no_disponible: true };
  assert.equal(seQuito(quitado), true);
  assert.equal(seQuito(sinEquipo), false);
  assert.equal(sinTrabajoHoy([quitado, sinEquipo]), true);
  assert.equal(sinTrabajoHoy([quitado, disponible]), false);
  assert.equal(sinTrabajoHoy([]), false);
});

test("de un ejercicio quitado solo se explica por qué se quitó", () => {
  const explicacion = [{ regla: "respeto_programa_entrenador" }, { regla: "dolor_reportado" }];
  assert.deepEqual(razonesVisibles({ objetivos: { series: 0 }, explicacion }), [{ regla: "dolor_reportado" }]);
  assert.deepEqual(razonesVisibles({ objetivos: { series: 2 }, explicacion }), explicacion);
  const sinFreno = [{ regla: "respeto_programa_entrenador" }];
  assert.deepEqual(razonesVisibles({ objetivos: { series: 0 }, explicacion: sinFreno }), sinFreno);
  assert.deepEqual(razonesVisibles({ objetivos: { series: 2 } }), []);
});

test("cada operación anuncia lo que hizo", () => {
  assert.equal(mensajeDeOperacion({ chequeo: { id: "c" } }), "Chequeo guardado.");
  assert.equal(mensajeDeOperacion({ serie_realizada: { id: "s" } }), "Serie guardada.");
  assert.equal(mensajeDeOperacion({ sustitucion: { id: "s" } }), "Sustitución guardada.");
  assert.equal(mensajeDeOperacion({ dolor_reportado: { id: "d" } }), "Dolor reportado guardado. Se avisó al entrenador.");
  assert.equal(mensajeDeOperacion({ sesion_realizada: { id: "r" } }), "Sesión iniciada.");
  assert.equal(mensajeDeOperacion({ sesion_realizada: { id: "r" } }, { avisando: true }), "Aviso enviado a tu entrenador.");
});
