import test from "node:test";
import assert from "node:assert/strict";
import { prepararMedidas } from "./series.js";

test("fuerza conserva el texto decimal y envía repeticiones enteras", () => {
  assert.deepEqual(prepararMedidas(["repeticiones", "carga"], { repeticiones: "10", carga: "20.50" }),
    { repeticiones: 10, carga: "20.50" });
});

test("cardio solo envía duración y distancia, sin exigir fuerza", () => {
  assert.deepEqual(prepararMedidas(["duracion", "distancia"], { duracion: "120", distancia: "1500.25" }),
    { duracion: 120, distancia: "1500.25" });
});

test("medidas vacías, fraccionarias, no finitas o negativas se rechazan antes del POST", () => {
  for (const [medida, valor] of [["repeticiones", ""], ["repeticiones", "1.5"], ["duracion", "0"],
    ["carga", "NaN"], ["carga", "Infinity"], ["carga", "1.001"], ["carga", "-1"], ["distancia", "0"]]) {
    assert.throws(() => prepararMedidas([medida], { [medida]: valor }));
  }
});


test("RIR opcional conserva cero y admite hasta diez", () => {
  for (const rir of [0, 2, 5, 10]) assert.deepEqual(prepararMedidas([], { rir: String(rir) }), { rir });
  assert.deepEqual(prepararMedidas([], { rir: "" }), {});
  for (const rir of ["-1", "11", "1.5", "NaN"]) assert.throws(() => prepararMedidas([], { rir }));
});
