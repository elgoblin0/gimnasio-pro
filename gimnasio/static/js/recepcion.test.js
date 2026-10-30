import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./recepcion.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/iniciar\(\);\s*$/, "");

function preparar() {
  const elementos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, {
      open: false, isConnected: true, textContent: "", hijos: [],
      addEventListener() {}, focus() {}, show() { this.open = true; },
      close() { this.open = false; },
      replaceChildren() { this.hijos = []; }, append(hijo) { this.hijos.push(hijo); },
    });
    return elementos.get(selector);
  };
  const consultas = [];
  let operacion;
  const contexto = vm.createContext({
    document: { querySelector: obtener, querySelectorAll: () => [],
      createElement: () => ({}), addEventListener() {} },
    window: { addEventListener() {} }, registrarPwa() {},
    crearControlDeOperacion: () => ({ comenzar: () => operacion, finalizar() {} }),
    formatearFechaHora: (fecha) => fecha,
    llamarApi: async (ruta, opciones) => {
      if (opciones) return { ocupacion: {}, visitas: [] };
      consultas.push(ruta);
      return { socio: {}, visita_abierta: consultas.length === 1 ? { desde: "entrada", minutos: 5 } : null,
        ultima_visita: { desde: "entrada", hasta: "salida" }, permanencia_habitual: {} };
    },
  });
  vm.runInContext(codigo, contexto);
  return { obtener, consultas, ejecutar: (texto) => vm.runInContext(texto, contexto),
    operar: async (ruta) => { operacion = { ruta, cuerpo: {} }; await vm.runInContext("enviar()", contexto); } };
}

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
