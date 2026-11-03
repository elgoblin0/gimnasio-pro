import assert from "node:assert/strict";
import { test } from "node:test";

import {
  avanceDeSesion,
  describirObjetivos,
  describirVolumen,
  ejercicioEnFoco,
  estadoDelDia,
  formatearDuracion,
  mensajeDeOperacion,
  proximoPaso,
  razonesVisibles,
  seQuito,
  sinTrabajoHoy,
} from "./entrenamiento-textos.js";

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

const ejercicioDe = (id, realizado, pendiente, extra = {}) => ({ id, realizado, pendiente, no_disponible: false, objetivos: { series: realizado + pendiente }, ...extra });

test("el foco es el primero pendiente, salvo que el socio elija otro que todavía tenga trabajo", () => {
  const ejercicios = [ejercicioDe("a", 3, 0), ejercicioDe("b", 0, 2), ejercicioDe("c", 0, 2)];
  assert.equal(ejercicioEnFoco(ejercicios, null), "b");
  assert.equal(ejercicioEnFoco(ejercicios, "c"), "c");
  assert.equal(ejercicioEnFoco(ejercicios, "a"), "b");
});

test("no hay foco en ejercicios quitados o no disponibles", () => {
  const ejercicios = [ejercicioDe("a", 0, 2, { no_disponible: true }), { ...ejercicioDe("b", 0, 2), objetivos: { series: 0 } }];
  assert.equal(ejercicioEnFoco(ejercicios, "a"), null);
});

test("el avance no cuenta las series de un ejercicio quitado", () => {
  const ejercicios = [ejercicioDe("a", 1, 2), { ...ejercicioDe("b", 0, 3), objetivos: { series: 0 } }];
  assert.deepEqual(avanceDeSesion(ejercicios), { hechas: 1, total: 3, texto: "1 de 3 series" });
});

test("el día queda listo cuando no hay series pendientes", () => {
  const sesion_planificada = { nombre: "Fuerza A" };
  assert.deepEqual(estadoDelDia({ sesion_planificada, series: [{}], ejercicios: [ejercicioDe("a", 1, 0)] }), {
    pendientes: false, titulo: "Listo por hoy", texto: "Fuerza A: 1 serie guardada.",
  });
  const empezada = estadoDelDia({ sesion_planificada, series: [{}, {}], ejercicios: [ejercicioDe("a", 2, 1)] });
  assert.equal(empezada.titulo, "Tenés una sesión empezada");
  assert.equal(empezada.pendientes, true);
});

test("la duración se redondea a minutos", () => {
  assert.equal(formatearDuracion(30), "menos de 1 min");
  assert.equal(formatearDuracion(2520), "42 min");
  assert.equal(formatearDuracion(3900), "1 h 5 min");
});

test("el volumen muestra solo lo que se hizo", () => {
  assert.equal(describirVolumen({ series: 6, repeticiones: 60, duracion: 0, distancia: "0" }), "6 series · 60 repeticiones");
  assert.equal(describirVolumen({ series: 1, repeticiones: 0, duracion: 1200, distancia: "1500.00" }), "1 serie · 20 min · 1.500 m");
});

test("el próximo paso nombra la sesión o el fin del programa", () => {
  assert.equal(proximoPaso({ sesion_planificada: { id: "b", nombre: "Fuerza B" }, explicacion: [] }, "a"), "Tu próxima sesión es Fuerza B.");
  assert.equal(proximoPaso({ sesion_planificada: { id: "a", nombre: "Fuerza A" }, explicacion: [] }, "a"), "Te quedan series de Fuerza A para la próxima vez.");
  assert.match(proximoPaso({ sesion_planificada: null, explicacion: [{ regla: "secuencia_realizada" }] }), /Terminaste tu programa/);
  assert.match(proximoPaso({ sesion_planificada: null, explicacion: [{ regla: "sin_programa" }] }), /asignar un programa/);
});
