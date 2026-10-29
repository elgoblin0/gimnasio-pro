import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { textoMotivoSustitucion } from "./sustituciones.js";

test("cada motivo que admite la tabla de sustituciones tiene su texto", () => {
  const migracion = readFileSync(new URL("../../../../migraciones/0012_sustituciones.sql", import.meta.url), "utf8");
  const motivos = migracion.match(/motivo IN \(([^)]+)\)/)[1].match(/'([a-z_]+)'/g).map((m) => m.slice(1, -1));
  assert.ok(motivos.includes("restriccion_salud"));
  for (const motivo of motivos) assert.notEqual(textoMotivoSustitucion(motivo), motivo);
});

test("la restricción de salud no se presenta como máquina ocupada", () => {
  assert.equal(textoMotivoSustitucion("restriccion_salud"), "restricción registrada por tu entrenador");
  assert.equal(textoMotivoSustitucion("maquina_ocupada"), "máquina ocupada");
});
