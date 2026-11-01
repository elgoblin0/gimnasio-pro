import assert from "node:assert/strict";
import test from "node:test";
import { textoSemana, textosCambios, textosCumplido, textosPendientes } from "./resumen-semanal-textos.js";

const VOLUMEN_VACIO = { repeticiones: 0, duracion: 0, distancia: "0" };

test("la semana se nombra por su lunes y su domingo", () => {
  assert.equal(textoSemana({ lunes: "2026-10-19", domingo: "2026-10-25" }), "Semana del 19/10 al 25/10");
});

test("lo cumplido compara con lo planificado y omite el volumen que no hubo", () => {
  assert.deepEqual(textosCumplido({
    sesiones_realizadas: 1, sesiones_planificadas: 3, series: 4, volumen: { repeticiones: 44, duracion: 0, distancia: "0" }, visitas: 1,
  }), ["1 de 3 sesiones planificadas", "4 series", "44 repeticiones", "1 visita"]);
  assert.deepEqual(textosCumplido({
    sesiones_realizadas: 0, sesiones_planificadas: 0, series: 0, volumen: VOLUMEN_VACIO, visitas: 0,
  }), ["0 sesiones realizadas", "0 series", "0 visitas"]);
});

test("duración en minutos y distancia en metros", () => {
  const textos = textosCumplido({
    sesiones_realizadas: 1, sesiones_planificadas: 1, series: 1, volumen: { repeticiones: 0, duracion: 150, distancia: "1500.25" }, visitas: 2,
  });
  assert.deepEqual(textos.slice(2, 4), ["2,5 min", "1.500,25 m"]);
});

test("los cambios usan la explicación guardada; sin ella, el nombre del freno", () => {
  assert.deepEqual(textosCambios({
    ajustes: [{ regla: "subir_carga", datos: { explicacion: "Subís 2,5 kg en Sentadilla." } }],
    frenos: [{ regla: "restriccion_salud", datos: { ejercicio_id: "ep" } }],
  }), ["Subís 2,5 kg en Sentadilla.", "Actuó el freno por restricción de salud"]);
});

test("los pendientes nombran el ejercicio y las sesiones sin realizar", () => {
  assert.deepEqual(textosPendientes({
    series: [{ nombre: "Sentadilla", series: [3] }],
    sesiones_sin_realizar: 2,
  }), ["Sentadilla: 1 serie sin hacer", "2 sesiones planificadas sin realizar"]);
  assert.deepEqual(textosPendientes({ series: [], sesiones_sin_realizar: 0 }), []);
});
