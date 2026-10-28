import { test } from "node:test";
import assert from "node:assert/strict";
import { crearDescanso } from "./descanso.js";

test("cuenta segundos completos y anuncia terminado sin negativos", () => {
  const descanso = crearDescanso(90, 1000);
  assert.deepEqual(descanso.consultar(1000), { restantes: 90, terminado: false });
  assert.equal(descanso.consultar(1501).restantes, 90);
  assert.equal(descanso.consultar(2000).restantes, 89);
  assert.deepEqual(descanso.consultar(91000), { restantes: 0, terminado: true });
  assert.equal(descanso.consultar(100000).restantes, 0);
});
test("saltea y suma treinta segundos incluso después de terminar", () => {
  const descanso = crearDescanso(60, 0);
  descanso.sumar30(1000);
  assert.equal(descanso.consultar(1000).restantes, 89);
  descanso.saltear(2000);
  assert.equal(descanso.consultar(2000).terminado, true);
  descanso.sumar30(5000);
  assert.equal(descanso.consultar(5000).restantes, 30);
});
test("duración cero termina de inmediato", () => {
  assert.equal(crearDescanso(0, 100).consultar(100).terminado, true);
});
