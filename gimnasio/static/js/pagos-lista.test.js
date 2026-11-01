import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./pagos.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/iniciar\(\)\.catch\([\s\S]*$/, "");

function crear(etiqueta, propiedades = {}, ...hijos) {
  return { etiqueta, ...propiedades, hijos, eventos: {},
    append(...nuevos) { this.hijos.push(...nuevos); },
    replaceChildren(...nuevos) { this.hijos = nuevos; },
    addEventListener(nombre, funcion) { this.eventos[nombre] = funcion; },
  };
}

function preparar(pagos = []) {
  const elementos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, crear("div"));
    return elementos.get(selector);
  };
  const llamadas = [];
  let fallo;
  const contexto = vm.createContext({
    URLSearchParams, Intl, Date, crear, registrarPwa() {},
    location: { search: "" }, document: { querySelector: obtener },
    crypto: { randomUUID: () => `clave-${llamadas.length}` },
    FormData: class { constructor() { return [["desde", "2026-10-27"], ["hasta", "2026-10-28"]]; } },
    formatearGuaranies: (monto) => `₲ ${monto}`, formatearFecha: String,
    llamarApi: async (ruta, opciones) => {
      llamadas.push({ ruta, opciones });
      if (fallo) throw fallo;
      return { pagos, total: 250000 };
    },
  });
  vm.runInContext(codigo, contexto);
  return { obtener, llamadas, cargar: () => contexto.cargarLista(), fallar: (error) => { fallo = error; } };
}

const pago = { id: "pago", socio: "Socio ficticio", tipo: "Mensual", medio: "efectivo", monto: 250000,
  autor: "Recepción ficticia", registrado_en: "2026-10-28T02:00:00+00:00", anulacion: null };

test("lista filtra fechas y muestra total, socio y motivo sin interpretar HTML", async () => {
  const pantalla = preparar([pago, { ...pago, id: "anulado", anulacion: { motivo: "<b>Error ficticio</b>" } }]);
  await pantalla.cargar();
  assert.equal(pantalla.llamadas[0].ruta, "/api/pagos?desde=2026-10-27&hasta=2026-10-28");
  assert.equal(pantalla.obtener("[data-total-pagos]").textContent, "Total sin anulados: ₲ 250000");
  const filas = pantalla.obtener("[data-lista-pagos]").hijos;
  assert.equal(filas[0].hijos[0].hijos[0], "Socio ficticio");
  assert.equal(filas[1].hijos.at(-1).hijos[0], "Anulado: <b>Error ficticio</b>");
  assert.equal(filas[1].hijos.some((hijo) => hijo.etiqueta === "form"), false);
});

test("anulación incierta conserva motivo y clave hasta confirmar el reintento", async () => {
  const pantalla = preparar([pago]);
  await pantalla.cargar();
  const formulario = pantalla.obtener("[data-lista-pagos]").hijos[0].hijos.at(-1);
  const motivo = formulario.hijos[0].hijos[1];
  motivo.value = "Error ficticio";
  pantalla.fallar({ estadoHttp: 0, message: "Sin conexión" });
  await formulario.eventos.submit({ preventDefault() {} });
  assert.equal(motivo.disabled, true);
  const primerEnvio = pantalla.llamadas.at(-1);
  motivo.value = "Otro texto";
  pantalla.fallar(null);
  await formulario.eventos.submit({ preventDefault() {} });
  const segundoEnvio = pantalla.llamadas.at(-2);
  assert.deepEqual(segundoEnvio, primerEnvio);
  assert.equal(primerEnvio.ruta, "/api/pagos/pago/anular");
  assert.equal(primerEnvio.opciones.cuerpo.motivo, "Error ficticio");
});

test("lista vacía y error de consulta tienen estados y permiten volver a consultar", async () => {
  const pantalla = preparar();
  await pantalla.cargar();
  assert.equal(pantalla.obtener("[data-lista-estado]").textContent, "No hay pagos en estas fechas.");
  pantalla.fallar(new Error("Sin conexión"));
  await pantalla.cargar();
  assert.equal(pantalla.obtener("[data-lista-error]").textContent, "Sin conexión");
  pantalla.fallar(null);
  await pantalla.cargar();
  assert.equal(pantalla.obtener("[data-lista-error]").textContent, "");
});
