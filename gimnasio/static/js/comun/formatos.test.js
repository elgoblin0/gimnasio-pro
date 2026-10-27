import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import * as formatos from "./formatos.js";

// JSON.parse conserva el texto original de cada número para leer los enteros grandes sin redondear.
const vectores = JSON.parse(
  readFileSync(new URL("../../../../pruebas/vectores/formatos.json", import.meta.url), "utf8"),
  (clave, valor, contexto) => typeof valor === "number" && Number.isInteger(valor) && !Number.isSafeInteger(valor)
    ? BigInt(contexto.source)
    : valor,
);

for (const [nombre, casos] of Object.entries(vectores)) {
  const nombreJs = nombre.replace(/_([a-z])/g, (_, letra) => letra.toUpperCase());
  test(`${nombre}: al menos ocho vectores, con entradas válidas e inválidas`, () => {
    assert.ok(casos.length >= 8);
    assert.ok(casos.some((caso) => caso.error));
    assert.ok(casos.some((caso) => "salida" in caso));
    assert.equal(typeof formatos[nombreJs], "function");
  });
  for (const [indice, caso] of casos.entries()) {
    test(`${nombre}: vector ${indice}`, () => {
      const ejecutar = () => "zona" in caso
        ? formatos[nombreJs](caso.entrada, caso.zona)
        : formatos[nombreJs](caso.entrada);
      if (caso.error) assert.throws(ejecutar, Error);
      else assert.equal(ejecutar(), caso.salida);
    });
  }
}
