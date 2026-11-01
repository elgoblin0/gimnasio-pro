import assert from "node:assert/strict";
import test from "node:test";
import { textoDia, textosDeHitos, textosDeRiesgo } from "./acompanamiento-textos.js";

test("el día se muestra sobre los 90 de la incorporación", () => {
  assert.equal(textoDia(45), "Día 45 de 90");
});

test("cada hito dice si se cumplió", () => {
  const hitos = textosDeHitos({ programa_asignado: true, primera_visita: false, primera_sesion: false });
  assert.deepEqual(hitos.map((hito) => hito.cumplido), [true, false, false]);
  assert.equal(hitos[2].texto, "Primera sesión realizada");
});

test("las razones del riesgo se explican con sus datos", () => {
  assert.deepEqual(textosDeRiesgo([
    { regla: "ausencia", datos: { dias: "20", umbral: "14" } },
    { regla: "tendencia", datos: { recientes: "2", anteriores: "8" } },
    { regla: "membresia_vencida", datos: { hasta: "2026-10-31" } },
  ]), ["20 días sin venir", "Bajó de 8 a 2 visitas en cuatro semanas", "Membresía vencida el 31/10/2026"]);
});
