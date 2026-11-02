import { test } from "node:test";
import assert from "node:assert/strict";

function prepararDocumento() {
  const destino = () => ({ replaceChildren() {}, append() {} });
  const partes = { "[data-horarios-hoy]": destino(), "[data-horarios-manana]": destino(), "[data-horarios-estado]": { textContent: "" } };
  const bloque = { hidden: true, querySelector: (selector) => partes[selector] };
  globalThis.document = {
    querySelector: () => bloque,
    createElement: () => ({ append() {}, set textContent(_) {} }),
  };
  return { bloque, estado: partes["[data-horarios-estado]"] };
}

// api.js toma `fetch` una sola vez, al cargarse: cada prueba cambia lo que hay detrás.
let pedir;
globalThis.fetch = (ruta) => pedir(ruta);

function prepararApi(respuestas) {
  const pedidos = [];
  pedir = async (ruta) => {
    pedidos.push(ruta);
    const respuesta = respuestas.shift();
    if (!respuesta) throw new Error("Sin conexión");
    return { ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => respuesta, text: async () => JSON.stringify(respuesta) };
  };
  return pedidos;
}

const DATOS = { hoy: { cerrado: true }, manana: { cerrado: true } };

test("no vuelve a pedir la previsión mientras está vigente, y sí cuando vence", async (t) => {
  t.mock.timers.enable({ apis: ["Date"] });
  prepararDocumento();
  const pedidos = prepararApi([DATOS, DATOS]);
  const { actualizarMejoresHorarios } = await import("./horarios.js?vigencia");
  await actualizarMejoresHorarios();
  await actualizarMejoresHorarios();
  assert.equal(pedidos.length, 1);
  t.mock.timers.tick(10 * 60_000);
  await actualizarMejoresHorarios();
  assert.equal(pedidos.length, 2);
});

test("si la consulta falla, la próxima vuelve a intentarla", async () => {
  const { estado } = prepararDocumento();
  const pedidos = prepararApi([]);
  const { actualizarMejoresHorarios } = await import("./horarios.js?falla");
  await actualizarMejoresHorarios();
  assert.match(estado.textContent, /No se pudieron cargar/);
  await actualizarMejoresHorarios();
  assert.equal(pedidos.length, 2);
});
