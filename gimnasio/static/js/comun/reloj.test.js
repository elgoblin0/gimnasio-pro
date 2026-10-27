import assert from "node:assert/strict";
import test from "node:test";

import { crearReloj } from "./reloj.js";

test("el reloj del sistema consulta el momento en cada llamada", (contexto) => {
  contexto.mock.timers.enable({ apis: ["Date"], now: 1645557742000 });
  const reloj = crearReloj();
  assert.equal(reloj.ahora().toISOString(), "2022-02-22T19:22:22.000Z");
  contexto.mock.timers.tick(1000);
  assert.equal(reloj.ahora().toISOString(), "2022-02-22T19:22:23.000Z");
});

test("el reloj fijo conserva el momento aunque avance el sistema", (contexto) => {
  contexto.mock.timers.enable({ apis: ["Date"], now: 1645557742000 });
  const reloj = crearReloj({ fijo: "2026-10-25T23:59:59-03:00" });
  contexto.mock.timers.tick(86400000);
  assert.equal(reloj.ahora().toISOString(), "2026-10-26T02:59:59.000Z");
});

test("cada lectura fija devuelve una fecha independiente de la entrada y de otras lecturas", () => {
  const entrada = new Date("2026-10-26T03:00:00Z");
  const reloj = crearReloj({ fijo: entrada });
  entrada.setUTCFullYear(2030);
  reloj.ahora().setUTCFullYear(2040);
  assert.equal(reloj.ahora().toISOString(), "2026-10-26T03:00:00.000Z");
});

test("acepta el inicio de la época y rechaza fechas fijas inválidas", () => {
  assert.equal(crearReloj({ fijo: 0 }).ahora().getTime(), 0);
  assert.throws(() => crearReloj({ fijo: "fecha inválida" }), RangeError);
});
