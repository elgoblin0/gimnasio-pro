import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ZONAS_CUERPO, crearSelectorZonas } from "./zonas.js";

test("14 zonas del vector compartido con el motor, con nombres visibles", () => {
  const vector = JSON.parse(readFileSync(new URL("../../../../pruebas/vectores/zonas_cuerpo.json", import.meta.url), "utf8"));
  assert.equal(ZONAS_CUERPO.length, 14);
  assert.deepEqual(ZONAS_CUERPO.map((z) => z.id), vector);
  assert.equal(new Set(ZONAS_CUERPO.map((z) => z.nombre)).size, 14);
  assert.equal(ZONAS_CUERPO.find((z) => z.id === "rodillas").nombre, "Rodillas");
});

// Documento mínimo: ejercita los eventos y atributos sin agregar dependencias.
function documentoDePrueba() {
  const documento = {
    createElementNS(espacio, nombre) {
      return {
        namespaceURI: espacio, nombre, ownerDocument: documento,
        atributos: {}, hijos: [], eventos: {},
        setAttribute(clave, valor) { this.atributos[clave] = valor; },
        getAttribute(clave) { return this.atributos[clave]; },
        append(...hijos) { this.hijos.push(...hijos); },
        addEventListener(tipo, funcion) { this.eventos[tipo] = funcion; },
      };
    },
  };
  return documento.createElementNS("", "div");
}

test("cada zona es un control accesible, seleccionable por clic, toque y teclado", () => {
  const contenedor = documentoDePrueba();
  const selector = crearSelectorZonas(contenedor);
  const controles = contenedor.hijos[0].hijos.filter((e) => e.getAttribute("role") === "checkbox");
  assert.equal(controles.length, 14);
  for (const [indice, control] of controles.entries()) {
    assert.equal(control.getAttribute("aria-label"), ZONAS_CUERPO[indice].nombre);
    assert.equal(control.getAttribute("tabindex"), "0");
    control.eventos.click(); // Los navegadores despachan clic también después de un toque.
    assert.equal(control.getAttribute("aria-checked"), "true");
    let evitado = false;
    control.eventos.keydown({ key: " ", preventDefault() { evitado = true; } });
    assert.equal(evitado, true);
    assert.equal(control.getAttribute("aria-checked"), "false");
    control.eventos.keydown({ key: "Enter", preventDefault() {} });
  }
  assert.deepEqual(selector.zonas(), ZONAS_CUERPO.map((z) => z.id));
  selector.deshabilitar(true);
  controles[0].eventos.click();
  assert.equal(selector.zonas().length, 14);
  assert.equal(controles[0].getAttribute("tabindex"), "-1");
  selector.deshabilitar(false);
  controles[0].eventos.keydown({ key: "Escape", preventDefault() { assert.fail(); } });
  controles[0].eventos.click();
  assert.equal(selector.zonas().length, 13);
});
