import { test } from "node:test";
import assert from "node:assert/strict";
import {
  candidatosDeAlternativa, ejerciciosDelEquipo, mensajeLegible, motivoDeRechazo, moverEnLista, nombreDeEquipo, sinAlternativaDisponible,
} from "./equipos-datos.js";

test("el equipo se muestra bien escrito aunque el catálogo guarde su clave", () => {
  assert.equal(nombreDeEquipo("cajon"), "cajón");
  assert.equal(nombreDeEquipo("barra"), "barra");
});

const remo = { id: "r", nombre: "Remo en polea", equipo: "polea", patron_movimiento: "tracción", alternativas: ["m"], estado_equipo: "disponible" };
const mancuernas = { id: "m", nombre: "Remo con mancuernas", equipo: "mancuernas", patron_movimiento: "tracción", alternativas: [], estado_equipo: "fuera_de_servicio" };
const banda = { id: "b", nombre: "Remo con banda", equipo: "banda", patron_movimiento: "tracción", alternativas: [], estado_equipo: "disponible" };
const otraPolea = { id: "o", nombre: "Remo alto", equipo: "polea", patron_movimiento: "tracción", alternativas: [], estado_equipo: "disponible" };
const sentadilla = { id: "s", nombre: "Sentadilla", equipo: "barra", patron_movimiento: "sentadilla", alternativas: [], estado_equipo: "disponible" };
const catalogo = [remo, mancuernas, banda, otraPolea, sentadilla];
const porId = new Map(catalogo.map((ejercicio) => [ejercicio.id, ejercicio]));

test("explica por qué un ejercicio no puede ser alternativa", () => {
  assert.equal(motivoDeRechazo(remo, banda), null);
  assert.equal(motivoDeRechazo(remo, otraPolea), "mismo equipo");
  assert.equal(motivoDeRechazo(remo, sentadilla), "otro patrón de movimiento");
});

test("ofrece primero las válidas y no repite las que ya están", () => {
  assert.deepEqual(candidatosDeAlternativa(remo, catalogo).map(({ candidato, motivo }) => [candidato.id, motivo]), [
    ["b", null],
    ["o", "mismo equipo"],
    ["s", "otro patrón de movimiento"],
  ]);
});

test("detecta el ejercicio cuyas alternativas no están disponibles", () => {
  assert.equal(sinAlternativaDisponible(remo, porId), true);
  assert.equal(sinAlternativaDisponible({ ...remo, alternativas: ["m", "b"] }, porId), false);
  assert.equal(sinAlternativaDisponible(sentadilla, porId), true);
});

test("cambia el identificador del rechazo por el nombre del ejercicio", () => {
  const id = "01a190f5-7dde-7000-8000-000000000b3c";
  const nombres = new Map([[id, { nombre: "Sentadilla" }]]);
  assert.equal(mensajeLegible(`${id}: debe tener distinto equipo.`, nombres), "Sentadilla: debe tener distinto equipo.");
  assert.equal(mensajeLegible(`${id}: el ejercicio no existe.`, new Map()), "El ejercicio: el ejercicio no existe.");
});

test("mover respeta los extremos de la lista", () => {
  assert.deepEqual(moverEnLista(["a", "b"], 1, -1), ["b", "a"]);
  assert.deepEqual(moverEnLista(["a", "b"], 0, -1), ["a", "b"]);
  assert.deepEqual(moverEnLista(["a", "b"], 1, 1), ["a", "b"]);
});

test("agrupa los ejercicios por el equipo que usan", () => {
  assert.deepEqual(ejerciciosDelEquipo({ nombre: "polea" }, catalogo).map((e) => e.id), ["r", "o"]);
});
