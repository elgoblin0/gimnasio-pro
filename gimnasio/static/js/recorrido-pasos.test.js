import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DURACION_NARRACION_MS, DURACION_PASO_MS, PASOS, cambioDeSesion, destino, esUltimo, iniciarRecorrido, leerRecorrido,
  pasoActual, progreso, siguiente, textoDeNarracion, textoDelPaso,
} from "./recorrido-pasos.js";

test("el recorrido tiene unos 7 pasos y cierra con el resumen de la sesión de Lucía", () => {
  assert.ok(PASOS.length >= 6 && PASOS.length <= 8);
  assert.equal(PASOS[0].id, "inicio");
  assert.equal(PASOS.at(-1).id, "resumen");
  assert.equal(PASOS.at(-1).pagina, "/resumen-sesion.html");
  assert.equal(PASOS.at(-1).sesion, "socio");
  assert.equal(new Set(PASOS.map((paso) => paso.id)).size, PASOS.length);
});

test("el tiempo de lectura deja lugar a las cargas dentro de los dos minutos", () => {
  const narraciones = PASOS.filter((paso) => textoDeNarracion(paso.id)).length;
  const lectura = (PASOS.length - 1) * DURACION_PASO_MS + narraciones * DURACION_NARRACION_MS;
  assert.ok(lectura <= 90_000, `${lectura} ms de lectura dejan menos de 30 s para cargar las pantallas`);
});

test("el primer paso no ancla nada: quien apretó el botón sigue viendo la portada como estaba", () => {
  assert.deepEqual(PASOS[0].ancla, []);
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
  assert.equal(cambioDeSesion(porId.inicio, porId.entrada), "recepcion");
  assert.equal(cambioDeSesion(porId.entrada, porId.escena), null);
  assert.equal(cambioDeSesion(porId.escena, porId.chequeo), "socio");
  assert.equal(cambioDeSesion(porId.series, porId.freno), "entrenador");
  assert.equal(cambioDeSesion(porId.freno, porId.resumen), "socio");
  assert.equal(cambioDeSesion(undefined, porId.inicio), null);
  // Entre pasos de la misma pantalla no hay navegación: la sesión es la misma.
  for (let i = 1; i < PASOS.length; i++) {
    if (PASOS[i].pagina === PASOS[i - 1].pagina) assert.equal(cambioDeSesion(PASOS[i - 1], PASOS[i]), null);
  }
});

test("la bandeja abre la hoja de Lucía y el resumen, la sesión que ella registró", () => {
  const freno = PASOS.find((paso) => paso.id === "freno");
  const resumen = PASOS.find((paso) => paso.id === "resumen");
  assert.equal(destino(freno, { lucia: "01a2" }), "/bandeja.html?socio=01a2");
  assert.equal(destino(freno, {}), "/bandeja.html");
  assert.equal(destino(resumen, { sesion: "01b3" }), "/resumen-sesion.html?sesion=01b3");
  assert.equal(destino(resumen, {}), "/resumen-sesion.html");
  assert.equal(destino(PASOS[1], { lucia: "01a2" }), "/recepcion.html");
});

test("cada paso tiene pocas frases, también al anunciar lo que va a pasar", () => {
  for (const paso of PASOS) {
    for (const texto of [textoDelPaso(paso.id), textoDeNarracion(paso.id)].filter(Boolean)) {
      assert.ok(texto.length > 20 && texto.length < 200, paso.id);
      assert.ok((texto.match(/[.!?](\s|$)/g) ?? []).length <= 3, paso.id);
    }
  }
});

test("la entrada anuncia a Lucía, se adapta a lo que encontró y explica la tarjeta contextual", () => {
  assert.equal(textoDeNarracion("entrada", { ocupacion: 12, aforo: 60 }),
    "Esto ve recepción: la ocupación de la sede al minuto, 12 de 60 lugares. Llega Lucía.");
  const registrada = textoDelPaso("entrada", { resultado: "registrada", ocupacion: 13, aforo: 60 });
  assert.match(registrada, /la ocupación pasa a 13 de 60/);
  assert.match(registrada, /tarjeta contextual/);
  const adentro = textoDelPaso("entrada", { resultado: "ya-adentro" });
  assert.match(adentro, /^Lucía ya está adentro/);
  assert.match(adentro, /tarjeta contextual/);
  for (const motivo of ["No hay lugar.", "No hay lugar"]) {
    assert.equal(textoDelPaso("entrada", { resultado: "rechazada", motivo }),
      "Hoy no se pudo registrar la entrada de Lucía: No hay lugar. El recorrido sigue igual.");
  }
  assert.equal(textoDelPaso("entrada", { resultado: "rechazada" }), "Hoy no se pudo registrar la entrada de Lucía. El recorrido sigue igual.");
});

test("la escena habla de figuras y no pide tocar nada: el paso avanza solo", () => {
  assert.match(textoDelPaso("escena", { conEscena: true }), /cada figura es una persona/);
  assert.doesNotMatch(textoDelPaso("escena", { conEscena: true }), /Tocá/);
  assert.match(textoDelPaso("escena", { conEscena: false }), /modo sin efectos/);
});

test("el chequeo cuenta antes que Lucía durmió mal y después qué cambió", () => {
  assert.match(textoDeNarracion("chequeo"), /durmió mal, sueño 1 de 5/);
  assert.match(textoDelPaso("chequeo", { chequeo: "guardado" }), /Como durmió mal, la propuesta/);
  assert.doesNotMatch(textoDelPaso("chequeo", {}), /durmió mal/);
});

test("los demás pasos dicen lo que pasó, también si otra visita se adelantó", () => {
  assert.match(textoDelPaso("series", { resultado: "registrada", ejercicio: "Remo ficticio", series: 2 }), /registra 2 series, la primera de Remo ficticio/);
  assert.match(textoDelPaso("series", { resultado: "registrada", ejercicio: "Remo ficticio", series: 1 }), /registra una serie, la primera de Remo ficticio/);
  assert.match(textoDelPaso("series", { resultado: "rechazada", motivo: "Sin conexión" }), /no se pudo guardar: Sin conexión\. La sesión/);
  assert.match(textoDeNarracion("freno"), /freno de seguridad/);
  assert.match(textoDelPaso("freno", { resultado: "revisado" }), /no se deshace/);
  assert.match(textoDelPaso("freno", { resultado: "ya-revisado" }), /ya los revisó/);
});

test("el resumen cierra con el cuerpo iluminado y no promete récords que no hubo", () => {
  assert.match(textoDelPaso("resumen", { zonas: 5, records: 1 }), /cuerpo se ilumina.*bate un récord personal/);
  assert.match(textoDelPaso("resumen", { zonas: 5, records: 2 }), /bate 2 récords personales/);
  assert.match(textoDelPaso("resumen", { zonas: 5, records: 0 }), /no batió récords/);
  assert.doesNotMatch(textoDelPaso("resumen", {}), /ilumina/);
  for (const hechos of [{ zonas: 5, records: 1 }, { zonas: 5, records: 0 }, {}]) assert.match(textoDelPaso("resumen", hechos), /Terminá el recorrido/);
});
