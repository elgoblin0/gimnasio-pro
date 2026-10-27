import assert from "node:assert/strict";
import test from "node:test";

import { registrarPwa } from "./pwa.js";

function preparar(t, { espera = false, falla = false, controlador = {} } = {}) {
  const anterior = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  const documentoAnterior = globalThis.document;
  const aviso = { hidden: true };
  const estado = { textContent: "" };
  const gestores = {};
  const registro = {
    waiting: espera ? {} : null,
    installing: { addEventListener: (evento, gestor) => { gestores[evento] = gestor; } },
    addEventListener: (evento, gestor) => { gestores[evento] = gestor; },
  };
  const llamadas = [];
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: {
    serviceWorker: {
      controller: controlador,
      register: async (...argumentos) => {
        llamadas.push(argumentos);
        if (falla) throw new TypeError("Sin red");
        return registro;
      },
    },
  } });
  globalThis.document = { querySelector: (selector) => selector === "[data-actualizacion]" ? aviso : estado };
  t.after(() => {
    Object.defineProperty(globalThis, "navigator", anterior);
    if (documentoAnterior === undefined) delete globalThis.document;
    else globalThis.document = documentoAnterior;
  });
  return { aviso, estado, registro, gestores, llamadas };
}

test("registra en la raíz y avisa de una versión que ya espera sin recargar", async (t) => {
  const { aviso, llamadas } = preparar(t, { espera: true });
  await registrarPwa();
  assert.deepEqual(llamadas, [["/sw.js", { scope: "/", updateViaCache: "none" }]]);
  assert.equal(aviso.hidden, false);
});

test("avisa al terminar de instalar una actualización y no en la primera instalación", async (t) => {
  const { aviso, registro, gestores } = preparar(t);
  await registrarPwa();
  gestores.updatefound();
  gestores.statechange();
  assert.equal(aviso.hidden, true);
  registro.waiting = {};
  gestores.statechange();
  assert.equal(aviso.hidden, false);
});

test("la primera instalación no muestra aviso de actualización", async (t) => {
  const { aviso } = preparar(t, { espera: true, controlador: null });
  await registrarPwa();
  assert.equal(aviso.hidden, true);
});

test("el fallo de registro informa que se requiere conexión", async (t) => {
  const { estado } = preparar(t, { falla: true });
  await registrarPwa();
  assert.match(estado.textContent, /Se requiere conexión a Internet/);
});
