import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigoSondeo = readFileSync(new URL("./comun/sondeo.js", import.meta.url), "utf8")
  .replaceAll("export function", "function");

const codigo = readFileSync(new URL("./recepcion.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/iniciar\(\);\s*$/, "");

function preparar(t) {
  const elementos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, {
      open: false, isConnected: true, textContent: "", hijos: [], style: { setProperty() {} },
      addEventListener() {}, focus() {}, show() { this.open = true; },
      close() { this.open = false; },
      replaceChildren() { this.hijos = []; }, append(hijo) { this.hijos.push(hijo); },
    });
    return elementos.get(selector);
  };
  const consultas = [];
  let operacion;
  let enCurso = false;
  let liberarOperacion;
  const lecturas = [];
  const contexto = vm.createContext({
    document: { querySelector: obtener, querySelectorAll: () => [],
      createElement: () => ({}), addEventListener() {}, removeEventListener() {} },
    window: { addEventListener() {} }, registrarPwa() {},
    setTimeout, clearTimeout, AbortController,
    actualizarMejoresHorarios() {}, crearSondeo: () => ({}),
    Option: class {},
    crearControlDeOperacion: () => ({
      get enCurso() { return enCurso; },
      comenzar() { enCurso = true; return operacion; },
      finalizar() { enCurso = false; },
    }),
    formatearFechaHora: (fecha) => fecha,
    llamarApi: async (ruta, opciones) => {
      if (opciones) {
        if (t) await new Promise((resolver) => { liberarOperacion = resolver; });
        return { ocupacion: {}, visitas: [] };
      }
      if (ruta === "/api/sesion") return { usuario: { rol: "recepcion" } };
      if (ruta === "/api/estado" || ruta === "/api/ocupacion") return {};
      if (ruta === "/api/visitas?abiertas=1") return { visitas: [] };
      if (ruta === "/api/visitas/socios") return { socios: [] };
      consultas.push(ruta);
      return { socio: {}, visita_abierta: consultas.length === 1 ? { desde: "entrada", minutos: 5 } : null,
        ultima_visita: { desde: "entrada", hasta: "salida" }, permanencia_habitual: {} };
    },
  });
  if (t) {
    contexto.fetch = async (ruta) => {
      lecturas.push(ruta);
      return { status: 200, json: async () => ruta === "/api/ocupacion" ? {} : { visitas: [] },
        headers: { get: () => null } };
    };
    vm.runInContext(codigoSondeo, contexto);
  }
  vm.runInContext(codigo, contexto);
  return { obtener, consultas, lecturas, liberar: () => liberarOperacion(),
    ejecutar: (texto) => vm.runInContext(texto, contexto),
    operar: async (ruta) => { operacion = { ruta, cuerpo: {} }; await vm.runInContext("enviar()", contexto); } };
}

test("el sondeo espera al POST aunque transcurran cinco segundos", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const pantalla = preparar(t);
  const vaciar = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
  await pantalla.ejecutar("iniciar()");
  t.after(() => pantalla.ejecutar("sondeos.forEach(sondeo => sondeo.detener())"));
  await vaciar();
  const lecturas = pantalla.lecturas.length;
  const envio = pantalla.operar("/api/entradas");
  await pantalla.ejecutar("actualizar()");
  t.mock.timers.tick(5000);
  await vaciar();
  assert.equal(pantalla.lecturas.length, lecturas);
  pantalla.liberar();
  await envio;
  t.mock.timers.tick(5000);
  await vaciar();
  assert.equal(pantalla.lecturas.length, lecturas + 2);
});

for (const ruta of ["/api/salidas", "/api/visitas/visita/conciliacion"]) {
  test(`actualiza la tarjeta abierta al confirmar ${ruta}`, async () => {
    const pantalla = preparar();
    await pantalla.ejecutar('abrirTarjeta("socio")');
    await pantalla.operar(ruta);
    assert.deepEqual(pantalla.consultas, ["/api/socios/socio/tarjeta", "/api/socios/socio/tarjeta"]);
    const textos = pantalla.obtener("[data-tarjeta-datos]").hijos.map((hijo) => hijo.textContent);
    assert.ok(textos.some((texto) => texto.startsWith("Última visita:")));
    assert.ok(!textos.some((texto) => texto.startsWith("Visita abierta")));
  });
}

test("una salida no vuelve a abrir una tarjeta cerrada", async () => {
  const pantalla = preparar();
  await pantalla.ejecutar('abrirTarjeta("socio")');
  pantalla.obtener("[data-tarjeta-contextual]").close();
  await pantalla.operar("/api/salidas");
  assert.equal(pantalla.consultas.length, 1);
  assert.equal(pantalla.obtener("[data-tarjeta-contextual]").open, false);
});

test("la escena se inicia después de mostrar los datos de recepción", async () => {
  const pantalla = preparar();
  pantalla.obtener("[data-contenido]").hidden = true;
  pantalla.ejecutar(`
    iniciarEscena = () => {
      globalThis.ocultaAlIniciarEscena = document.querySelector('[data-contenido]').hidden;
    };
  `);
  await pantalla.ejecutar("iniciar()");
  assert.equal(pantalla.ejecutar("ocultaAlIniciarEscena"), false);
  assert.equal(pantalla.obtener("[data-estado]").textContent, "Recepción lista.");
});

for (const consulta of ["/api/ocupacion", "/api/visitas?abiertas=1", "/api/visitas/socios"]) {
  test('inicia la escena al recuperar la primera lectura fallida de ' + consulta, async () => {
    const pantalla = preparar();
    pantalla.ejecutar(`
      globalThis.apiOriginal = llamarApi;
      globalThis.esperas = 0;
      setTimeout = () => { esperas++; };
      llamarApi = async (ruta, opciones) => {
        if (ruta === ${JSON.stringify(consulta)}) throw new Error('Lectura fallida');
        return apiOriginal(ruta, opciones);
      };
    `);
    await pantalla.ejecutar("iniciar()");
    assert.equal(pantalla.ejecutar("escenaIniciada"), false);
    pantalla.ejecutar("llamarApi = apiOriginal");
    assert.equal(await pantalla.ejecutar("actualizar()"), true);
    assert.equal(pantalla.ejecutar("escenaIniciada"), true);
    assert.equal(pantalla.obtener("[data-contenido]").hidden, false);
    await pantalla.ejecutar("actualizar()");
    assert.equal(pantalla.ejecutar("esperas"), 1);
  });
}
