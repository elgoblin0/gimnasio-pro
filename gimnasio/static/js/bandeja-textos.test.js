import { test } from "node:test";
import assert from "node:assert/strict";
import {
  antiguedad, avisosSinRevisar, contarSocios, explicacionDeAviso, motivosPorSocio, sociosConNovedad, textoFreno, textosDeMotivos,
} from "./bandeja-textos.js";

test("resume los motivos de un socio sin repetir filas, en orden de prioridad", () => {
  assert.deepEqual(textosDeMotivos([
    { tipo: "aviso_progresion" },
    { tipo: "aviso_seguridad" },
    { tipo: "aviso_seguridad" },
    { tipo: "ejercicio_sin_alternativa" },
  ]), ["2 avisos por dolor o restricción", "Ejercicio sin alternativa", "Aviso por chequeo o tope"]);
});

test("la antigüedad no retrocede si el reloj de la sede va adelante del navegador", () => {
  const ahora = Date.parse("2026-10-31T12:00:00Z");
  assert.equal(antiguedad("2026-10-31T12:30:00+00:00", ahora), "recién");
  assert.equal(antiguedad("2026-10-31T11:59:40+00:00", ahora), "recién");
  assert.equal(antiguedad("2026-10-31T11:15:00+00:00", ahora), "hace 45 min");
  assert.equal(antiguedad("2026-10-31T07:00:00+00:00", ahora), "hace 5 h");
  assert.equal(antiguedad("2026-10-30T11:00:00+00:00", ahora), "hace 1 día");
  assert.equal(antiguedad("2026-10-20T11:00:00+00:00", ahora), "hace 11 días");
});

test("sin el texto del freno quedan el nombre del freno y el ejercicio", () => {
  const nombres = { e1: "Remo sin equipo" };
  const aviso = { freno: "restriccion_salud", explicacion: [{ datos: { ejercicio_id: "e1" } }, { datos: { ejercicio_id: "e1" } }] };
  assert.deepEqual(explicacionDeAviso(aviso, (id) => nombres[id]), { textos: [], ejercicios: ["Remo sin equipo"] });
  assert.equal(textoFreno(aviso.freno), "Restricción de salud");
  assert.equal(textoFreno("otro"), "Aviso al entrenador");
});

test("con consentimiento conserva la explicación del motor una sola vez", () => {
  const aviso = { explicacion: [{ datos: { explicacion: "Bajó la carga por dolor." } }, { datos: { explicacion: "Bajó la carga por dolor." } }] };
  assert.deepEqual(explicacionDeAviso(aviso).textos, ["Bajó la carga por dolor."]);
});

test("un aviso nuevo es novedad aunque el socio ya estuviera en la bandeja", () => {
  const antes = [{ tipo: "aviso_seguridad", socios: [{ id: "s1", motivos: [{ tipo: "aviso_seguridad", aviso_id: "a1" }] }] }];
  const despues = [{ tipo: "aviso_seguridad", socios: [
    { id: "s1", motivos: [{ tipo: "aviso_seguridad", aviso_id: "a1" }, { tipo: "aviso_seguridad", aviso_id: "a2" }] },
    { id: "s2", motivos: [{ tipo: "sin_programa" }] },
  ] }];
  const anteriores = motivosPorSocio(antes);
  assert.deepEqual(sociosConNovedad(anteriores, antes), []);
  assert.deepEqual(sociosConNovedad(anteriores, despues).map((s) => s.id), ["s1", "s2"]);
  assert.equal(contarSocios(despues), 2);
});

test("revisar solo alcanza a los avisos sin revisar", () => {
  assert.deepEqual(avisosSinRevisar([{ id: "a1", revisado: true }, { id: "a2", revisado: false }]).map((a) => a.id), ["a2"]);
});
