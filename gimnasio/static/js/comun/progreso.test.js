import test from "node:test";
import assert from "node:assert/strict";
import { calcularProgreso } from "./progreso.js";
const tamaño = { ancho: 600, alto: 280 };
test("vacío sin trazo ni marcas", () => {
  const resultado = calcularProgreso([], tamaño);
  assert.equal(resultado.trazo, "");
  assert.deepEqual(resultado.marcas, []);
  assert.equal(resultado.escalas.inicio, null);
});
test("un punto queda centrado y admite carga cero", () => {
  const resultado = calcularProgreso([{ fecha_local: "2026-10-01", carga: "0.00" }], tamaño);
  assert.equal(resultado.marcas[0].x, 316);
  assert.equal(resultado.marcas[0].y, 240);
  assert.equal(resultado.trazo, "M316,240");
});
test("varios puntos conservan intervalos de fecha y escala de carga", () => {
  const resultado = calcularProgreso([
    { fecha_local: "2026-10-01", carga: "10" },
    { fecha_local: "2026-10-02", carga: "20" },
    { fecha_local: "2026-10-05", carga: "40" },
  ], tamaño);
  assert.deepEqual(resultado.marcas.map(({x, y}) => [x, y]), [[52,185],[184,130],[580,20]]);
  assert.equal(resultado.trazo, "M52,185 L184,130 L580,20");
});
