import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./pagos.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/iniciar\(\)\.catch\([\s\S]*$/, "");

function preparar(error, socio = "") {
  const elementos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, {
      disabled: false, hidden: true, value: "", textContent: "",
      replaceChildren() {}, addEventListener() {},
    });
    return elementos.get(selector);
  };
  const formulario = { datos: { socio_id: "socio", tipo_id: "tipo", medio: "efectivo", monto: "" },
    querySelector: () => obtener("fieldset"), reset() {} };
  elementos.set("[data-pago]", formulario);
  const envios = [];
  let fallo = error;
  const avisos = [];
  const contexto = vm.createContext({
    URLSearchParams, location: { search: socio ? `?socio=${socio}` : "", origin: "https://gimnasio.test" },
    window: { parent: { postMessage: (...argumentos) => avisos.push(argumentos) } },
    document: { querySelector: obtener }, registrarPwa() {},
    crypto: { randomUUID: () => String(envios.length + 1) },
    FormData: class { constructor() { return Object.entries(formulario.datos); } },
    crear() {}, formatearGuaranies: String, formatearFecha: String,
    llamarApi: async (ruta, opciones) => {
      envios.push(JSON.parse(JSON.stringify(opciones)));
      if (typeof fallo === "function") await fallo();
      else if (fallo) throw fallo;
      return { monto: 250000, membresia: { desde: "desde", hasta: "hasta" } };
    },
    evento: { preventDefault() {}, target: formulario },
  });
  vm.runInContext(codigo, contexto);
  return { obtener, formulario, envios, avisos,
    registrar: () => vm.runInContext("registrar(evento)", contexto),
    reintentar: () => vm.runInContext("enviar()", contexto),
    resolver: () => { fallo = null; } };
}

for (const error of [{ estadoHttp: 0 }, { estadoHttp: 422 }]) {
  test(`pago contextual conserva socio y formulario ante fallo ${error.estadoHttp}`, async () => {
    const pantalla = preparar(error, "socio-fijado");
    await pantalla.registrar();
    assert.equal(pantalla.envios[0].cuerpo.socio_id, "socio-fijado");
    assert.equal(pantalla.formulario.datos.tipo_id, "tipo");
    assert.equal(pantalla.avisos.at(-1)[0].tipo, error.estadoHttp === 0 ? "pago-en-curso" : "pago-libre");
    pantalla.resolver();
    if (error.estadoHttp === 0) await pantalla.reintentar();
    else await pantalla.registrar();
    assert.ok(pantalla.avisos.some(([aviso]) => aviso.tipo === "pago-registrado"));
    assert.equal(pantalla.avisos.at(-1)[0].tipo, "pago-libre");
  });
}

for (const error of [
  { estadoHttp: 0, codigo: "conexion_requerida" },
  { estadoHttp: 503, codigo: "error" },
  { estadoHttp: 409, codigo: "solicitud_en_curso" },
]) {
  test(`resultado incierto ${error.estadoHttp}: conserva cuerpo y clave hasta reintentar`, async () => {
    const pantalla = preparar(error);
    await pantalla.registrar();
    assert.equal(pantalla.obtener("fieldset").disabled, true);
    assert.equal(pantalla.obtener("[data-recargar]").disabled, true);
    assert.equal(pantalla.obtener("[data-reintentar-pago]").hidden, false);
    pantalla.formulario.datos.monto = "250000";
    await pantalla.registrar();
    assert.equal(pantalla.envios.length, 1);
    pantalla.resolver();
    await pantalla.reintentar();
    assert.deepEqual(pantalla.envios[1], pantalla.envios[0]);
    assert.equal(pantalla.obtener("fieldset").disabled, false);
    assert.equal(pantalla.obtener("[data-reintentar-pago]").hidden, true);
    await pantalla.registrar();
    assert.notEqual(pantalla.envios[2].clave, pantalla.envios[0].clave);
  });
}

test("un rechazo definitivo permite corregir el pago", async () => {
  const pantalla = preparar({ estadoHttp: 422, codigo: "monto_invalido" });
  await pantalla.registrar();
  assert.equal(pantalla.obtener("fieldset").disabled, false);
  pantalla.formulario.datos.monto = "250000";
  pantalla.resolver();
  await pantalla.registrar();
  assert.notEqual(pantalla.envios[1].clave, pantalla.envios[0].clave);
});

test("no permite envios simultaneos ni recargar mientras se registra el pago", async () => {
  let terminar;
  const espera = new Promise((resolver) => { terminar = resolver; });
  const pantalla = preparar(() => espera);
  const envio = pantalla.registrar();
  await pantalla.registrar();
  await pantalla.reintentar();
  assert.equal(pantalla.envios.length, 1);
  assert.equal(pantalla.obtener("fieldset").disabled, true);
  assert.equal(pantalla.obtener("[data-recargar]").disabled, true);
  terminar();
  await envio;
  assert.equal(pantalla.obtener("fieldset").disabled, false);
  assert.equal(pantalla.obtener("[data-recargar]").disabled, false);
});
