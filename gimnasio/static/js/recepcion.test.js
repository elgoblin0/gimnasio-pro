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
  const eventos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, {
      open: false, isConnected: true, textContent: "", hijos: [], style: { setProperty() {} },
      eventos: {}, addEventListener(nombre, accion) { this.eventos[nombre] = accion; }, focus() {}, show() { this.open = true; },
      close() { this.open = false; },
      replaceChildren() { this.hijos = []; }, append(...hijos) {
        for (const hijo of hijos) {
          this.hijos.push(hijo);
          if (hijo.dataset?.pagoTarjeta !== undefined) elementos.set("[data-pago-tarjeta]", hijo);
          if (hijo.dataset?.descartarPago !== undefined) elementos.set("[data-descartar-pago]", hijo);
        }
      },
    });
    return elementos.get(selector);
  };
  const consultas = [];
  let operacion;
  let enCurso = false;
  let liberarOperacion;
  const lecturas = [];
  const contexto = vm.createContext({
    document: { querySelector: (selector) => selector === "[data-pago-tarjeta]" ? elementos.get(selector) ?? null : obtener(selector), querySelectorAll: () => [],
      createElement: () => ({ dataset: {}, style: {}, eventos: {},
        addEventListener(nombre, accion) { this.eventos[nombre] = accion; },
        append(...hijos) { for (const hijo of hijos) this.hijos.push(hijo); },
        remove() { elementos.delete("[data-pago-tarjeta]"); },
      }), addEventListener() {}, removeEventListener() {} },
    window: { addEventListener: (nombre, accion) => eventos.set(nombre, accion) }, registrarPwa() {},
    location: { origin: "https://gimnasio.test" },
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
  return { obtener, consultas, lecturas, eventos, retirarFormulario: () => elementos.delete("[data-pago-tarjeta]"), liberar: () => liberarOperacion(),
    ejecutar: (texto) => vm.runInContext(texto, contexto),
    operar: async (ruta) => { operacion = { ruta, cuerpo: {} }; await vm.runInContext("enviar()", contexto); } };
}

test("la tarjeta muestra el aviso como texto y lo retira al revocar", async () => {
  const pantalla = preparar();
  pantalla.ejecutar('llamarApi = async () => ({ socio: {}, aviso_personal: "<b>Consultar al entrenador</b>", permanencia_habitual: {} });');
  await pantalla.ejecutar('abrirTarjeta("socio")');
  const contenido = pantalla.obtener("[data-tarjeta-datos]");
  assert.ok(contenido.hijos.some(hijo => hijo.textContent === "Aviso para el personal: <b>Consultar al entrenador</b>"));
  pantalla.ejecutar('llamarApi = async () => ({ socio: {}, aviso_personal: null, permanencia_habitual: {} });');
  await pantalla.ejecutar('abrirTarjeta("socio")');
  assert.ok(!contenido.hijos.some(hijo => hijo.textContent?.startsWith("Aviso para el personal:")));
});

test("al confirmar el pago refresca la tarjeta y mantiene el socio para la entrada", async () => {
  const pantalla = preparar();
  await pantalla.ejecutar('abrirTarjeta("socio")');
  const formulario = pantalla.obtener("[data-pago-tarjeta]");
  formulario.contentWindow = {};
  let retirado = false;
  formulario.remove = () => { retirado = true; pantalla.retirarFormulario(); };
  await pantalla.eventos.get("message")({ origin: "https://gimnasio.test", source: formulario.contentWindow, data: { tipo: "pago-registrado" } });
  assert.equal(retirado, true);
  assert.deepEqual(pantalla.consultas, ["/api/socios/socio/tarjeta", "/api/socios/socio/tarjeta"]);
  assert.ok(pantalla.obtener("[data-tarjeta-datos]").hijos.some(hijo => hijo.textContent === "Registrar entrada"));
  assert.equal(pantalla.ejecutar("socioTarjeta"), "socio");
});

  test("tarjeta con pago pendiente para recepción", async () => {
    const pantalla = preparar();
    pantalla.ejecutar(`

      llamarApi = async () => ({ socio: {}, pago_pendiente: true, permanencia_habitual: {} });
    `);
    await pantalla.ejecutar('abrirTarjeta("socio")');
    const textos = pantalla.obtener("[data-tarjeta-datos]").hijos.map(hijo => hijo.textContent);
    assert.ok(textos.includes("Pago pendiente"));
    assert.ok(textos.includes("Registrar pago"));
    assert.ok(textos.includes("Registrar entrada"));
  });

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
  t.mock.timers.tick(4999);
  await vaciar();
  pantalla.liberar();
  await envio;
  assert.equal(pantalla.lecturas.length, lecturas);
  // Al vencer el intervalo después del POST, el sondeo puede consultar de nuevo.
  t.mock.timers.tick(1);
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

test("seleccionar un socio sin visita permite pagar antes de registrar entrada", async () => {
  const pantalla = preparar();
  pantalla.ejecutar('llamarApi = async () => ({ socio: {}, pago_pendiente: true, membresia: { vigente: false }, permanencia_habitual: {} });');
  pantalla.obtener("#socio").value = "socio-vencido";
  await pantalla.obtener("#socio").eventos.change();
  assert.equal(pantalla.obtener("[data-tarjeta-contextual]").open, true);
  assert.equal(pantalla.ejecutar("socioTarjeta"), "socio-vencido");
  assert.ok(pantalla.obtener("[data-tarjeta-datos]").hijos.some(hijo => hijo.textContent === "Registrar pago"));
});

for (const ruta of ["/api/salidas", "/api/visitas/visita/conciliacion"]) {
  test(`conserva el formulario de pago al confirmar ${ruta} y al elegir otro socio`, async () => {
    const pantalla = preparar();
    await pantalla.ejecutar('abrirTarjeta("socio")');
    const formulario = pantalla.obtener("[data-pago-tarjeta]");
    const contenido = pantalla.obtener("[data-tarjeta-datos]");
    contenido.append(formulario);
    const hijos = [...contenido.hijos];
    await pantalla.operar(ruta);
    pantalla.obtener("[data-tarjeta-contextual]").close();
    await pantalla.ejecutar('abrirTarjeta("otro-socio")');
    assert.equal(pantalla.obtener("[data-tarjeta-contextual]").open, true);
    assert.equal(pantalla.ejecutar("socioTarjeta"), "socio");
    assert.deepEqual(contenido.hijos, hijos);
    assert.deepEqual(pantalla.consultas, ["/api/socios/socio/tarjeta"]);
  });
}

test("administracion no inicia la pantalla de recepcion", async () => {
  const pantalla = preparar();
  pantalla.ejecutar('llamarApi = async () => ({ usuario: { rol: "administracion" } });');
  await pantalla.ejecutar("iniciar()");
  assert.equal(pantalla.ejecutar("autorizada"), false);
});

for (const pendiente of [false, true]) {
  test("descartar pago respeta envio sin confirmar: " + pendiente, async () => {
    const pantalla = preparar();
    pantalla.ejecutar('llamarApi = async () => ({ socio: {}, pago_pendiente: true, permanencia_habitual: {} });');
    await pantalla.ejecutar('abrirTarjeta("socio")');
    const contenido = pantalla.obtener("[data-tarjeta-datos]");
    contenido.hijos.find(hijo => hijo.textContent === "Registrar pago").eventos.click();
    const formulario = pantalla.obtener("[data-pago-tarjeta]");
    formulario.contentWindow = {};
    const descartar = pantalla.obtener("[data-descartar-pago]");
    const avisar = tipo => pantalla.eventos.get("message")({
      origin: "https://gimnasio.test", source: formulario.contentWindow, data: { tipo },
    });
    await avisar("pago-en-curso");
    if (!pendiente) await avisar("pago-libre");
    assert.equal(Boolean(descartar.disabled), pendiente);
    await descartar.eventos.click();
    await pantalla.ejecutar('abrirTarjeta("otro")');
    assert.equal(pantalla.ejecutar("socioTarjeta"), pendiente ? "socio" : "otro");
  });
}
