import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./clases.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/iniciar\(\)\.catch\([\s\S]*$/, "");

function preparar(error) {
  const elementos = new Map();
  const documento = { querySelector: (selector) => obtener(selector), activeElement: null };
  const crear = (etiqueta, propiedades = {}, ...hijos) => ({
    etiqueta, ...propiedades, hijos, dataset: { focoAgenda: propiedades["data-foco-agenda"] },
    append(...nuevos) { this.hijos.push(...nuevos); },
    contains(elemento) { return this === elemento || this.hijos.some((hijo) => hijo?.contains?.(elemento)); },
    querySelectorAll() {
      return this.hijos.flatMap((hijo) => hijo?.etiqueta === "button" ? [hijo] : hijo?.querySelectorAll?.() ?? []);
    },
    replaceChildren(...nuevos) {
      if (this.contains(documento.activeElement)) documento.activeElement = null;
      this.hijos = nuevos;
    },
    focus() { documento.activeElement = this; },
  });
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, {
      ...crear("div"),
      disabled: false, hidden: true, value: "", textContent: "",
      addEventListener() {}, reset() {},
    });
    return elementos.get(selector);
  };
  const envios = [];
  const sondeos = [];
  let fallo = error;
  let siguienteClave = 0;
  const contexto = vm.createContext({
    document: documento, crear, registrarPwa() {},
    crearSondeo: (opciones) => {
      const sondeo = { ...opciones, detenido: false, detener() { this.detenido = true; } };
      sondeos.push(sondeo);
      return sondeo;
    },
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
    envios, obtener, sondeos, documento,
    ejecutar: (texto) => vm.runInContext(texto, contexto),
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

test("sondea la agenda del socio seleccionado y descarta el sondeo anterior", async () => {
  const pantalla = preparar();
  await pantalla.ejecutar('usuario = { rol: "recepcion" }; socios = []; cargar()');
  assert.equal(pantalla.sondeos[0].url, "/api/clases/agenda");
  pantalla.obtener("[data-socio]").value = "segundo";
  await pantalla.ejecutar("cargar()");
  assert.equal(pantalla.sondeos[0].detenido, true);
  assert.equal(pantalla.sondeos[1].url, "/api/clases/agenda?socio_id=segundo");
  pantalla.ejecutar("enCurso = true");
  assert.equal(pantalla.sondeos[1].puedeConsultar(), false);
  pantalla.ejecutar('enCurso = false; pendiente = { clave: "sin-confirmar" }');
  assert.equal(pantalla.sondeos[1].puedeConsultar(), false);
});

for (const rol of ["socio", "recepcion"]) {
  test(`el sondeo conserva el foco por ocurrencia y acción para ${rol}`, async () => {
    const pantalla = preparar();
    pantalla.obtener("[data-socio]").value = "socio";
    await pantalla.ejecutar(`usuario = { rol: "${rol}" }; socios = []; cargar()`);
    const actualizar = pantalla.sondeos[0].alCambiar;
    const primera = { clase_id: "clase", fecha: "2026-11-01", libres: 2 };
    const segunda = { ...primera, fecha: "2026-11-02" };
    const datos = (ocurrencias) => ({ desde: primera.fecha, hasta: segunda.fecha, ocurrencias });
    const lista = pantalla.obtener("[data-agenda]");
    actualizar(datos([primera, segunda]));
    const indice = rol === "socio" ? 1 : 4;
    const anterior = lista.querySelectorAll()[indice];
    anterior.focus();
    actualizar(datos([{ ...segunda, libres: 1 }, primera]));
    assert.ok(pantalla.documento.activeElement);
    assert.notEqual(pantalla.documento.activeElement, anterior);
    assert.equal(pantalla.documento.activeElement?.dataset.focoAgenda, anterior.dataset.focoAgenda);

    const externo = pantalla.obtener("[data-buscar-socio]");
    externo.focus();
    actualizar(datos([primera, segunda]));
    assert.equal(pantalla.documento.activeElement, externo);

    lista.querySelectorAll()[0].focus();
    actualizar(datos([{ ...primera, cancelada: true }, segunda]));
    assert.equal(pantalla.documento.activeElement, null);

    actualizar(datos([primera]));
    lista.querySelectorAll()[0].focus();
    actualizar(datos([{ ...primera, reserva: { id: "reserva", estado: "con_lugar" } }]));
    assert.equal(pantalla.documento.activeElement, null);
  });
}
