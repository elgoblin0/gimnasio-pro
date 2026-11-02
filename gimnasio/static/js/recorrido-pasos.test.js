import { test } from "node:test";
import assert from "node:assert/strict";

import {
  PASOS, cambioDeSesion, destino, esUltimo, iniciarRecorrido, leerRecorrido, pasoActual, progreso, siguiente,
  textoDelPaso,
} from "./recorrido-pasos.js";

test("el recorrido tiene entre 8 y 10 pasos y termina invitando a explorar sin sesión", () => {
  assert.ok(PASOS.length >= 8 && PASOS.length <= 10);
  assert.equal(PASOS[0].id, "inicio");
  assert.deepEqual(PASOS.at(-1), { id: "explorar", pagina: "/", sesion: "ninguna", ancla: ["[data-demo]", ".portada-ingreso"] });
  assert.equal(new Set(PASOS.map((paso) => paso.id)).size, PASOS.length);
});

test("avanza de a un paso y no pasa del último", () => {
  let estado = iniciarRecorrido();
  assert.equal(progreso(estado), `Paso 1 de ${PASOS.length}`);
  const vistos = [pasoActual(estado).id];
  while (!esUltimo(estado)) {
    estado = siguiente(estado);
    vistos.push(pasoActual(estado).id);
  }
  assert.deepEqual(vistos, PASOS.map((paso) => paso.id));
  assert.equal(siguiente(estado), null);
});

test("avanzar conserva la pausa y lo que el recorrido ya sabe", () => {
  const estado = { indice: 4, pausado: true, datos: { lucia: "0190" } };
  assert.deepEqual(siguiente(estado), { indice: 5, pausado: true, datos: { lucia: "0190" } });
});

test("lee el estado guardado y descarta lo que no entiende", () => {
  assert.deepEqual(leerRecorrido('{"indice":3,"pausado":true,"datos":{"lucia":"x"}}'), { indice: 3, pausado: true, datos: { lucia: "x" } });
  assert.deepEqual(leerRecorrido('{"indice":0}'), { indice: 0, pausado: false, datos: {} });
  for (const roto of [null, "", "{", "[]", '{"indice":-1}', `{"indice":${PASOS.length}}`, '{"indice":"2"}', '{"indice":1.5}']) {
    assert.equal(leerRecorrido(roto), null, String(roto));
  }
});

test("cambia de sesión solo cuando el paso nuevo pide otra", () => {
  const porId = Object.fromEntries(PASOS.map((paso) => [paso.id, paso]));
  assert.equal(cambioDeSesion(porId.inicio, porId.aforo), "recepcion");
  assert.equal(cambioDeSesion(porId.aforo, porId.entrada), null);
  assert.equal(cambioDeSesion(porId.escena, porId.propuesta), "socio");
  assert.equal(cambioDeSesion(porId.series, porId.freno), "entrenador");
  assert.equal(cambioDeSesion(porId.administracion, porId.explorar), "ninguna");
  assert.equal(cambioDeSesion(undefined, porId.inicio), null);
  // Entre pasos de la misma pantalla no hay navegación: la sesión es la misma.
  for (let i = 1; i < PASOS.length; i++) {
    if (PASOS[i].pagina === PASOS[i - 1].pagina && PASOS[i].sesion !== "ninguna") assert.equal(cambioDeSesion(PASOS[i - 1], PASOS[i]), null);
  }
});

test("la bandeja abre la hoja de Lucía cuando se conoce su id", () => {
  const freno = PASOS.find((paso) => paso.id === "freno");
  assert.equal(destino(freno, { lucia: "01a2" }), "/bandeja.html?socio=01a2");
  assert.equal(destino(freno, {}), "/bandeja.html");
  assert.equal(destino(PASOS[1], { lucia: "01a2" }), "/recepcion.html");
});

test("cada paso tiene una o dos frases", () => {
  for (const paso of PASOS) {
    const texto = textoDelPaso(paso.id);
    assert.ok(texto.length > 20 && texto.length < 200, paso.id);
    assert.ok((texto.match(/[.!?](\s|$)/g) ?? []).length <= 3, paso.id);
  }
});

test("la entrada se adapta a lo que encontró", () => {
  assert.equal(textoDelPaso("entrada", { resultado: "registrada", ocupacion: 13, aforo: 60 }),
    "Lucía llega y recepción registra su entrada: la ocupación pasa a 13 de 60.");
  assert.match(textoDelPaso("entrada", { resultado: "ya-adentro" }), /^Lucía ya está adentro/);
  for (const motivo of ["No hay lugar.", "No hay lugar"]) {
    assert.equal(textoDelPaso("entrada", { resultado: "rechazada", motivo }),
      "Hoy no se pudo registrar la entrada de Lucía: No hay lugar. El recorrido sigue igual.");
  }
  assert.equal(textoDelPaso("entrada", { resultado: "rechazada" }), "Hoy no se pudo registrar la entrada de Lucía. El recorrido sigue igual.");
});

test("los demás pasos dicen lo que pasó, también si otra visita se adelantó", () => {
  assert.match(textoDelPaso("aforo", { ocupacion: 12, aforo: 60 }), /12 de 60 lugares/);
  assert.match(textoDelPaso("escena", { conEscena: true }), /escena de ocupación/);
  assert.match(textoDelPaso("escena", { conEscena: false }), /modo sin efectos/);
  assert.match(textoDelPaso("propuesta", { chequeo: "guardado" }), /durmió mal/);
  assert.doesNotMatch(textoDelPaso("propuesta", {}), /durmió mal/);
  assert.match(textoDelPaso("series", { resultado: "registrada", ejercicio: "Remo ficticio" }), /serie de Remo ficticio/);
  assert.match(textoDelPaso("series", { resultado: "rechazada", motivo: "Sin conexión" }), /no se pudo guardar: Sin conexión\. La sesión/);
  assert.match(textoDelPaso("freno", { avisos: 1 }), /freno de seguridad/);
  assert.match(textoDelPaso("freno", { avisos: 0 }), /ya los revisó/);
  assert.match(textoDelPaso("revision", { resultado: "revisado" }), /no se deshace/);
  assert.match(textoDelPaso("revision", { resultado: "ya-revisado" }), /historial/);
});
