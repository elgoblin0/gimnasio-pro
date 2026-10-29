import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ZONAS_CUERPO, crearSelectorZonas, crearResumenZonas } from "./zonas.js";

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
        append(...hijos) { for (const hijo of hijos) { hijo.padre = this; this.hijos.push(hijo); } },
        removeAttribute(clave) { delete this.atributos[clave]; },
        get dataset() {
          return new Proxy({}, {
            get: (_, clave) => this.atributos[`data-${clave}`],
            set: (_, clave, valor) => { this.atributos[`data-${clave}`] = valor; return true; },
          });
        },
        querySelector(selector) { return this.hijos.find((h) => h.nombre === selector); },
        querySelectorAll() { return this.hijos.filter((h) => h.atributos["data-zona"]); },
        cloneNode() {
          const copia = documento.createElementNS(this.namespaceURI, this.nombre);
          copia.atributos = { ...this.atributos };
          copia.textContent = this.textContent;
          copia.append(...this.hijos.map((h) => h.cloneNode(true)));
          return copia;
        },
        replaceWith(otro) { this.padre.hijos[this.padre.hijos.indexOf(this)] = otro; },
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

test("el resumen conserva ambos estados en una zona y no ofrece controles de edición", () => {
  const contenedor = documentoDePrueba();
  crearResumenZonas(contenedor, ["cuadriceps"], ["cuadriceps", "rodillas"]);
  const svg = contenedor.hijos[0];
  assert.equal(svg.getAttribute("role"), "img");
  const controles = svg.querySelectorAll("[data-zona]");
  const cuadriceps = controles.find((c) => c.dataset.zona === "cuadriceps");
  assert.equal(cuadriceps.dataset.trabajada, "true");
  assert.equal(cuadriceps.dataset.dolor, "true");
  assert.match(cuadriceps.querySelector("text").textContent, /trabajada · con dolor/);
  for (const control of controles) {
    assert.equal(control.getAttribute("role"), undefined);
    assert.equal(control.getAttribute("tabindex"), undefined);
    assert.deepEqual(control.eventos, {});
  }
});

test("con movimiento reducido no se intenta crear WebGL y la selección sigue funcionando", () => {
  const contenedor = documentoDePrueba();
  contenedor.ownerDocument.defaultView = { matchMedia: () => ({ matches: true }) };
  contenedor.ownerDocument.createElement = () => assert.fail("no debe cargar efectos");
  const selector = crearSelectorZonas(contenedor);
  contenedor.hijos[0].querySelectorAll()[0].eventos.click();
  assert.deepEqual(selector.zonas(), ["pecho"]);
});

test("sin WebGL conserva la silueta seleccionable y los estados del resumen", () => {
  const contenedor = documentoDePrueba();
  contenedor.ownerDocument.defaultView = { matchMedia: () => ({ matches: false }) };
  contenedor.ownerDocument.createElement = () => ({ getContext: () => null });
  const selector = crearSelectorZonas(contenedor);
  contenedor.hijos[0].querySelectorAll()[0].eventos.keydown({ key: "Enter", preventDefault() {} });
  assert.deepEqual(selector.zonas(), ["pecho"]);
  const resumen = documentoDePrueba();
  resumen.ownerDocument.defaultView = contenedor.ownerDocument.defaultView;
  resumen.ownerDocument.createElement = contenedor.ownerDocument.createElement;
  crearResumenZonas(resumen, ["pecho"], ["pecho"]);
  const pecho = resumen.hijos[0].querySelectorAll()[0];
  assert.equal(pecho.dataset.trabajada, "true");
  assert.equal(pecho.dataset.dolor, "true");
});
