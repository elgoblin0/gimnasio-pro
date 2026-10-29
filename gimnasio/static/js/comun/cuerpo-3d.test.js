import { test } from "node:test";
import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { crearSelectorZonas } from "./zonas.js";

// Sustituye solo WebGL y la descarga: la selección y el relevo del foco son reales.
const moduloThree = `
  class Objeto {
    constructor() { this.position = { set() {} }; this.color = { set() {} }; }
    add() {} lookAt() {} updateProjectionMatrix() {} dispose() {}
    setPixelRatio() {} setSize() {} render() {}
  }
  export { Objeto as WebGLRenderer, Objeto as Scene, Objeto as Group,
    Objeto as PerspectiveCamera, Objeto as HemisphereLight,
    Objeto as DirectionalLight, Objeto as MeshStandardMaterial };
  export const DoubleSide = 2;
`;
const moduloModelo = `export class GLTFLoader {
  async loadAsync() { return { scene: { updateMatrixWorld() {}, traverse() {} } }; }
}`;
registerHooks({
  resolve(nombre, contexto, siguiente) {
    const codigo = nombre === "three" ? moduloThree : nombre.endsWith("/GLTFLoader.js") ? moduloModelo : null;
    return codigo === null ? siguiente(nombre, contexto) : {
      url: `data:text/javascript,${encodeURIComponent(codigo)}`, shortCircuit: true,
    };
  },
});
const { crearCuerpo } = await import("./cuerpo-3d.js");

function crearDocumento() {
  const documento = {
    defaultView: {
      devicePixelRatio: 1,
      matchMedia: () => ({ matches: false, addEventListener() {} }),
      MouseEvent: class { constructor(type) { this.type = type; } },
      MutationObserver: class { observe() {} },
      ResizeObserver: class { observe() {} },
    },
    createElement(nombre) { return this.createElementNS("", nombre); },
    createElementNS(namespaceURI, nombre) {
      return {
        ownerDocument: documento, namespaceURI, nombre, style: {},
        atributos: {}, hijos: [], eventos: {}, isConnected: true,
        get dataset() {
          return new Proxy({}, {
            get: (_, clave) => this.atributos[`data-${clave}`],
            set: (_, clave, valor) => { this.atributos[`data-${clave}`] = valor; return true; },
          });
        },
        setAttribute(clave, valor) { this.atributos[clave] = valor; },
        getAttribute(clave) { return this.atributos[clave]; },
        append(...hijos) { this.hijos.push(...hijos); },
        prepend(hijo) { this.hijos.unshift(hijo); },
        addEventListener(tipo, funcion) { this.eventos[tipo] = funcion; },
        dispatchEvent(evento) { this.eventos[evento.type]?.(evento); },
        click() { if (!this.disabled) this.dispatchEvent({ type: "click" }); },
        focus() { documento.activeElement = this; },
        getContext() { return null; },
        getBoundingClientRect() { return { width: 500 }; },
        querySelector(nombre) { return this.hijos.find(hijo => hijo.nombre === nombre); },
        querySelectorAll() { return this.hijos.filter(hijo => hijo.getAttribute("data-zona")); },
      };
    },
  };
  documento.body = documento.createElement("body");
  return documento;
}

function pulsar(elemento, tipo, tecla) {
  let evitado = false;
  elemento.dispatchEvent({ type: tipo, key: tecla, preventDefault() { evitado = true; } });
  // Un botón HTML activa su clic al soltar Espacio; un checkbox ARIA no lo hace.
  if (!evitado && tipo === "keyup" && tecla === " " && elemento.nombre === "button") elemento.click();
}

test("cargar el cuerpo 3D entre presionar y soltar Espacio conserva Rodillas seleccionada", async () => {
  const documento = crearDocumento();
  const contenedor = documento.createElement("div");
  const selector = crearSelectorZonas(contenedor);
  const svg = contenedor.querySelector("svg");
  const rodillas = svg.querySelectorAll().find(control => control.getAttribute("data-zona") === "rodillas");
  rodillas.focus();
  pulsar(rodillas, "keydown", " ");
  assert.deepEqual(selector.zonas(), ["rodillas"]);
  await crearCuerpo(contenedor, svg, true);
  const control = documento.activeElement;
  assert.notEqual(control, rodillas);
  assert.equal(control.dataset.zona, "rodillas");
  assert.equal(control.getAttribute("aria-checked"), "true");
  pulsar(control, "keyup", " ");
  assert.deepEqual(selector.zonas(), ["rodillas"]);
  // Tanto Espacio como Enter y el clic siguen alternando una sola vez.
  for (const tecla of [" ", "Enter"]) {
    pulsar(control, "keydown", tecla);
    pulsar(control, "keyup", tecla);
    assert.deepEqual(selector.zonas(), []);
    control.click();
    assert.deepEqual(selector.zonas(), ["rodillas"]);
  }
  selector.deshabilitar(true);
  pulsar(control, "keydown", " ");
  control.click();
  assert.deepEqual(selector.zonas(), ["rodillas"]);
});
