import { test } from "node:test";
import assert from "node:assert/strict";
import { crearSondeo, pausarSondeos } from "./sondeo.js";

test("200 entrega datos, 304 conserva ETag, pausa y reanuda, errores espacian hasta 30 s", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const documento = new EventTarget();
  documento.hidden = false;
  globalThis.document = documento;
  t.after(() => { delete globalThis.document; });
  const consultas = [];
  const cambios = [];
  let estado = 200;
  t.mock.method(globalThis, "fetch", async (url, opciones) => {
    consultas.push({ url, opciones });
    if (estado === 0) throw new TypeError("Sin red");
    return { status: estado, headers: new Headers({ ETag: '"1"' }), json: async () => ({ cantidad: 1 }) };
  });
  const vaciar = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
  const avanzar = async (ms) => { t.mock.timers.tick(ms); await vaciar(); };
  const sondeo = crearSondeo({ url: "/api/ocupacion", alCambiar: (datos) => cambios.push(datos) });
  await vaciar();
  assert.equal(cambios.length, 1);
  estado = 304;
  await avanzar(5000);
  assert.equal(cambios.length, 1);
  assert.equal(consultas[1].opciones.headers["If-None-Match"], '"1"');
  documento.hidden = true;
  documento.dispatchEvent(new Event("visibilitychange"));
  await avanzar(20000);
  assert.equal(consultas.length, 2);
  documento.hidden = false;
  documento.dispatchEvent(new Event("visibilitychange"));
  await vaciar();
  assert.equal(consultas.length, 3);
  estado = 0;
  await avanzar(5000);
  assert.equal(consultas.length, 4);
  await avanzar(9999);
  assert.equal(consultas.length, 4);
  await avanzar(1);
  assert.equal(consultas.length, 5);
  await avanzar(20000);
  assert.equal(consultas.length, 6);
  await avanzar(30000);
  assert.equal(consultas.length, 7);
  estado = 200;
  await avanzar(30000);
  await avanzar(5000);
  assert.equal(cambios.length, 3);
  sondeo.detener();
  await avanzar(30000);
  assert.equal(consultas.length, 9);
});

test("una respuesta anterior al registro no pisa su resultado y no hay consultas simultáneas", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let resolver;
  let consultas = 0;
  const cambios = [];
  t.mock.method(globalThis, "fetch", () => {
    consultas++;
    return new Promise((aceptar) => { resolver = aceptar; });
  });
  const sondeo = crearSondeo({ url: "/api/visitas", alCambiar: (datos) => cambios.push(datos) });
  t.after(() => sondeo.detener());
  await sondeo.actualizar();
  assert.equal(consultas, 1);
  sondeo.invalidar();
  resolver({ status: 200, headers: new Headers({ ETag: '"anterior"' }), json: async () => ({ visitas: [] }) });
  for (let i = 0; i < 8; i++) await Promise.resolve();
  assert.equal(cambios.length, 0);
  t.mock.timers.tick(5000);
  assert.equal(consultas, 2);
  sondeo.detener();
  resolver({ status: 200, headers: new Headers(), json: async () => ({ visitas: [] }) });
  for (let i = 0; i < 8; i++) await Promise.resolve();
  assert.equal(cambios.length, 0);
});

test("espera el permiso de consulta y descarta respuestas recibidas sin permiso", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let permitido = false;
  let resolver;
  const consultas = [];
  const cambios = [];
  t.mock.method(globalThis, "fetch", (url, opciones) => {
    consultas.push(opciones);
    return new Promise((aceptar) => { resolver = aceptar; });
  });
  const sondeo = crearSondeo({ url: "/api/ocupacion", puedeConsultar: () => permitido,
    alCambiar: (datos) => cambios.push(datos) });
  t.after(() => sondeo.detener());
  const vaciar = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
  t.mock.timers.tick(5000);
  assert.equal(consultas.length, 0);
  permitido = true;
  t.mock.timers.tick(5000);
  assert.equal(consultas.length, 1);
  permitido = false;
  resolver({ status: 200, headers: new Headers({ ETag: '"anterior"' }), json: async () => ({ cantidad: 0 }) });
  await vaciar();
  assert.equal(cambios.length, 0);
  permitido = true;
  t.mock.timers.tick(5000);
  assert.deepEqual(consultas[1].headers, {});
  resolver({ status: 200, headers: new Headers({ ETag: '"actual"' }), json: async () => ({ cantidad: 1 }) });
  await vaciar();
  assert.deepEqual(cambios, [{ cantidad: 1 }]);
});

test("pausar cancela la consulta en curso sin contarla como fallo y reanudar vuelve a consultar", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const senales = [];
  let fallos = 0;
  t.mock.method(globalThis, "fetch", (url, { signal }) => {
    senales.push(signal);
    return new Promise((aceptar, rechazar) => {
      signal.addEventListener("abort", () => rechazar(new DOMException("Cancelada", "AbortError")));
    });
  });
  const vaciar = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
  const sondeo = crearSondeo({ url: "/api/ocupacion", alCambiar() {}, alFallar: () => { fallos++; } });
  t.after(() => sondeo.detener());
  const reanudar = pausarSondeos();
  assert.equal(senales[0].aborted, true);
  await vaciar();
  assert.equal(fallos, 0);
  t.mock.timers.tick(60000);
  assert.equal(senales.length, 1);
  reanudar();
  assert.equal(senales.length, 2);
  assert.equal(senales[1].aborted, false);
});

test("pausar no reanuda un sondeo detenido por su pantalla", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let consultas = 0;
  t.mock.method(globalThis, "fetch", async () => {
    consultas++;
    return { status: 304 };
  });
  const sondeo = crearSondeo({ url: "/api/ocupacion", alCambiar() {} });
  for (let i = 0; i < 8; i++) await Promise.resolve();
  sondeo.detener();
  pausarSondeos()();
  t.mock.timers.tick(60000);
  assert.equal(consultas, 1);
});
