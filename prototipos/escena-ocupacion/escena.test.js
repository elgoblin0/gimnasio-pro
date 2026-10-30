import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const codigo = readFileSync(new URL('./escena.js', import.meta.url), 'utf8');
const datos = JSON.parse(readFileSync(new URL('./personas.json', import.meta.url), 'utf8'));

async function iniciar(reducido) {
  const elemento = () => ({
    style: {},
    setAttribute() {},
    addEventListener() {},
    append() {},
    remove() {},
    querySelectorAll: () => [],
  });
  const contexto = {
    scale() {}, fillRect() {}, strokeRect() {}, fillText() {},
    createLinearGradient: () => ({ addColorStop() {} }),
  };
  const elementos = new Map();
  const lienzo = { clientWidth: 1000, clientHeight: 800, getContext: () => contexto };
  let cuadro;
  let ahora = 0;
  const ventana = {};
  await runInNewContext(`(async () => {${codigo}\n})()`, {
    document: {
      body: { dataset: { escena: 'b' } },
      querySelector(selector) {
        if (selector === 'canvas') return lienzo;
        if (!elementos.has(selector)) elementos.set(selector, elemento());
        return elementos.get(selector);
      },
      createElement: elemento,
      addEventListener() {},
    },
    window: ventana,
    matchMedia: () => ({ matches: reducido }),
    fetch: async () => ({ json: async () => datos }),
    getComputedStyle: () => ({ getPropertyValue: () => '#ffffff' }),
    devicePixelRatio: 1,
    performance: { now: () => ahora },
    requestAnimationFrame: funcion => { cuadro = funcion; },
    setInterval() {},
    ResizeObserver: class { observe() {} },
  });
  return {
    prototipo: ventana.prototipo,
    completarMovimiento() { ahora += 1500; cuadro(ahora); },
  };
}

function verificarPosiciones(personas) {
  for (const persona of personas) {
    assert.ok(Number.isFinite(persona.posicion.x), `Visita ${persona.id}: coordenada horizontal inválida`);
    assert.ok(Number.isFinite(persona.posicion.y), `Visita ${persona.id}: coordenada vertical inválida`);
    if (persona.zona === 'En la sede') {
      assert.ok(persona.posicion.x >= 16 && persona.posicion.x <= 84);
      assert.equal(persona.posicion.y, 91);
    }
  }
}

for (const reducido of [false, true]) {
  test(`las visitas tienen coordenadas válidas desde la carga y tras los cambios (movimiento reducido: ${reducido})`, async () => {
    const escena = await iniciar(reducido);
    assert.equal(escena.prototipo.personas.length, 40);
    verificarPosiciones(escena.prototipo.personas);
    escena.completarMovimiento();
    for (let paso = 0; paso < 30; paso++) {
      escena.prototipo.avanzar();
      escena.completarMovimiento();
      verificarPosiciones(escena.prototipo.personas);
      for (const persona of escena.prototipo.personas) {
        assert.ok(!persona.hasta);
        assert.ok(Number.isFinite(parseFloat(persona.boton.style.left)));
        assert.ok(Number.isFinite(parseFloat(persona.boton.style.top)));
      }
    }
  });
}
