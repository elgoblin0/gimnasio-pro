import test from "node:test";
import assert from "node:assert/strict";
import { formatearCarga } from "./formatos.js";

test("la carga se presenta en kg sin alterar el decimal recibido", () => {
  assert.equal(formatearCarga("20.50"), "20,50 kg");
  assert.equal(formatearCarga(0), "0,00 kg");
  assert.equal(formatearCarga("1234.75"), "1.234,75 kg");
});

test("una carga ausente o no finita no se presenta como cero", () => {
  for (const valor of [null, undefined, "", true, NaN, Infinity, -1]) {
    assert.throws(() => formatearCarga(valor));
  }
});
