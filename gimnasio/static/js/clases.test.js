import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./clases.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/iniciar\(\)\.catch\([\s\S]*$/, "");

function preparar(error) {
  const elementos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, {
      disabled: false, hidden: true, value: "", textContent: "",
      replaceChildren() {}, addEventListener() {}, reset() {},
    });
    return elementos.get(selector);
  };
  const envios = [];
  let fallo = error;
  let siguienteClave = 0;
  const contexto = vm.createContext({
    document: { querySelector: obtener }, registrarPwa() {},
    crypto: { randomUUID: () => String(++siguienteClave) },
    llamarApi: async (ruta, opciones) => {
      if (!opciones) return { desde: "2026-10-26", hasta: "2026-11-08", ocurrencias: [] };
      envios.push(JSON.parse(JSON.stringify({ ruta, ...opciones })));
      if (typeof fallo === "function") await fallo();
      else if (fallo) throw fallo;
      return { id: "reserva" };
    },
  });
  vm.runInContext(`${codigo}\nusuario = { rol: "socio" };`, contexto);
  return {
    envios, obtener,
    enviar: (socio = "primero") => vm.runInContext(
      `escribir("/api/clases/reservas", "POST", { socio_id: ${JSON.stringify(socio)} }, $("[data-boton]"))`, contexto),
    reintentar: () => vm.runInContext(
      'escribir(pendiente.ruta, pendiente.metodo, pendiente.cuerpo, $("[data-reintentar-operacion]"))', contexto),
    resolver: () => { fallo = null; },
  };
}

for (const error of [
  { estadoHttp: 0, codigo: "conexion_requerida" },
  { estadoHttp: 503, codigo: "error" },
  { estadoHttp: 409, codigo: "solicitud_en_curso" },
]) {
  test(`reserva sin confirmar (${error.estadoHttp}): reintenta cuerpo y clave originales`, async () => {
    const pantalla = preparar(error);
    await pantalla.enviar();
    assert.equal(pantalla.obtener("[data-reintentar-operacion]").hidden, false);
    await pantalla.enviar("otro");
    assert.equal(pantalla.envios.length, 1);
    pantalla.resolver();
    await pantalla.reintentar();
    assert.deepEqual(pantalla.envios[1], pantalla.envios[0]);
    assert.equal(pantalla.obtener("[data-reintentar-operacion]").hidden, true);
  });
}

test("membresía renovada: un rechazo definitivo permite volver a intentar la reserva", async () => {
  const pantalla = preparar({ estadoHttp: 422, codigo: "membresia_no_vigente" });
  await pantalla.enviar();
  pantalla.resolver();
  await pantalla.enviar();
  assert.notEqual(pantalla.envios[0].clave, pantalla.envios[1].clave);
});

test("impide enviar dos reservas mientras la primera se confirma", async () => {
  let terminar;
  const espera = new Promise((resolver) => { terminar = resolver; });
  const pantalla = preparar(() => espera);
  const envio = pantalla.enviar();
  await pantalla.enviar();
  assert.equal(pantalla.envios.length, 1);
  terminar();
  await envio;
});
