import { test } from "node:test";
import assert from "node:assert/strict";
import { calcularVolumenPorZona, escalaRelativa, filasDeVolumen, separarRotulos, totalDeSeries } from "./volumen-zonas.js";

const ZONAS = { sentadilla: ["cuadriceps", "gluteos"], remo: ["dorsales", "biceps"], peso: ["cuadriceps"] };
const zonas = (id) => ZONAS[id] ?? [];

const rotulo = (id, izquierda, arriba) => ({ id, izquierda, arriba, ancho: 100, alto: 26 });

test("los rótulos que se pisan se separan sin mover al de arriba", () => {
  const [hombros, pecho, biceps] = separarRotulos([rotulo("pecho", 40, 110), rotulo("hombros", 0, 100), rotulo("biceps", 20, 112)]);
  assert.deepEqual([hombros.id, hombros.arriba], ["hombros", 100]);
  assert.deepEqual([pecho.id, pecho.arriba], ["pecho", 130]);
  assert.deepEqual([biceps.id, biceps.arriba], ["biceps", 160]);
});

test("los rótulos que no se cruzan quedan donde estaban", () => {
  const ubicados = separarRotulos([rotulo("izquierda", 0, 100), rotulo("derecha", 200, 100), rotulo("abajo", 0, 200)]);
  assert.deepEqual(ubicados.map(u => u.arriba), [100, 100, 200]);
});

test("cada serie cuenta completa en todas las zonas del ejercicio", () => {
  const volumen = calcularVolumenPorZona([{ ejercicios: [{ ejercicio_id: "sentadilla", series: 3 }] }], zonas);
  assert.deepEqual([...volumen], [["cuadriceps", 3], ["gluteos", 3]]);
});

test("suma todas las sesiones de la semana tipo", () => {
  const volumen = calcularVolumenPorZona([
    { ejercicios: [{ ejercicio_id: "sentadilla", series: 3 }, { ejercicio_id: "remo", series: 2 }] },
    { ejercicios: [{ ejercicio_id: "peso", series: 4 }] },
  ], zonas);
  assert.equal(volumen.get("cuadriceps"), 7);
  assert.equal(volumen.get("gluteos"), 3);
  assert.equal(volumen.get("dorsales"), 2);
});

test("una zona repetida en el catálogo no cuenta dos veces", () => {
  const volumen = calcularVolumenPorZona([{ ejercicios: [{ ejercicio_id: "x", series: 2 }] }], () => ["pecho", "pecho"]);
  assert.equal(volumen.get("pecho"), 2);
});

test("un campo de series a medio escribir no rompe el cuerpo", () => {
  const sesiones = [{ ejercicios: [{ ejercicio_id: "sentadilla", series: "" }, { ejercicio_id: "remo", series: "abc" }, { ejercicio_id: "peso", series: "2" }] }];
  assert.deepEqual([...calcularVolumenPorZona(sesiones, zonas)], [["cuadriceps", 2]]);
  assert.equal(totalDeSeries(sesiones), 2);
});

test("la escala es relativa al máximo del propio programa", () => {
  const escala = escalaRelativa(new Map([["pecho", 12], ["biceps", 3]]));
  assert.equal(escala.get("pecho"), 1);
  assert.equal(escala.get("biceps"), 0.25);
  assert.equal(escalaRelativa(new Map([["pecho", 2]])).get("pecho"), 1);
  assert.deepEqual([...escalaRelativa(new Map())], []);
});

test("las filas van de la zona más trabajada a la menos e incluyen las que no tienen series", () => {
  const filas = filasDeVolumen(new Map([["biceps", 2], ["cuadriceps", 8]]));
  assert.equal(filas[0].id, "cuadriceps");
  assert.equal(filas[0].relativa, 1);
  assert.equal(filas[1].id, "biceps");
  assert.equal(filas[2].series, 0);
  assert.equal(filas.length, 14);
});
