import test from "node:test";
import assert from "node:assert/strict";
import { calcularProgreso, escalaDeCargas, resumirProgreso } from "./progreso.js";
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
test("varios puntos conservan intervalos de fecha", () => {
  const resultado = calcularProgreso([
    { fecha_local: "2026-10-01", carga: "10" },
    { fecha_local: "2026-10-02", carga: "20" },
    { fecha_local: "2026-10-05", carga: "40" },
  ], tamaño);
  assert.deepEqual(resultado.marcas.map(({ x }) => x), [52, 184, 580]);
});
test("el eje no arranca en cero y la carga más baja no queda pegada al piso", () => {
  const { minima, maxima } = escalaDeCargas([20, 28]);
  assert.ok(minima > 15 && minima < 20);
  assert.ok(maxima > 28 && maxima < 32);
  const resultado = calcularProgreso([
    { fecha_local: "2026-10-01", carga: "20" },
    { fecha_local: "2026-10-05", carga: "28" },
  ], tamaño);
  const recorrido = resultado.escalas.abajo - resultado.escalas.arriba;
  // La suba ocupa más de la mitad del alto del gráfico.
  assert.ok(resultado.marcas[0].y - resultado.marcas[1].y > recorrido / 2);
});
test("una carga repetida queda dentro del gráfico", () => {
  const resultado = calcularProgreso([
    { fecha_local: "2026-10-01", carga: "20" },
    { fecha_local: "2026-10-05", carga: "20" },
  ], tamaño);
  const { arriba, abajo } = resultado.escalas;
  assert.ok(resultado.marcas.every(({ y }) => y > arriba && y < abajo));
});
test("el resumen da la última carga y el cambio", () => {
  assert.equal(resumirProgreso([]), null);
  assert.deepEqual(resumirProgreso([{ carga: "20" }, { carga: "28.5" }]), { ultima: 28.5, cambio: 8.5, sesiones: 2 });
});
