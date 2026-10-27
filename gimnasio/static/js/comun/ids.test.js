import assert from "node:assert/strict";
import test from "node:test";

let numeroPrueba = 0;
const formato = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

async function cargarGenerador() {
  // Cada prueba obtiene su propia secuencia, sin exponer estado en la API.
  return import(`./ids.js?prueba=${numeroPrueba++}`);
}

function fijarAleatorio(contexto, valor) {
  return contexto.mock.method(crypto, "getRandomValues", (datos) => {
    let restante = valor;
    for (let posicion = datos.length - 1; posicion >= 0; posicion--) {
      datos[posicion] = Number(restante & 255n);
      restante >>= 8n;
    }
    return datos;
  });
}

test("reproduce el vector UUIDv7 de la RFC 9562 con crypto.getRandomValues", async (contexto) => {
  contexto.mock.timers.enable({ apis: ["Date"], now: 1645557742000 });
  // Mismo vector del apéndice A.6 que en las pruebas Python.
  const aleatorio = (0xcc3n << 62n) | 0x18c4dc0c0c07398fn;
  const generarBits = fijarAleatorio(contexto, aleatorio);
  const { nuevoId } = await cargarGenerador();
  const identificador = nuevoId();
  assert.equal(identificador, "017f22e2-79b0-7cc3-98c4-dc0c0c07398f");
  assert.match(identificador, formato);
  assert.equal(generarBits.mock.callCount(), 1);
  assert.equal(generarBits.mock.calls[0].arguments[0].length, 10);
});

test("ordena UUIDv7 únicos en el mismo milisegundo y en milisegundos sucesivos", async (contexto) => {
  contexto.mock.timers.enable({ apis: ["Date"], now: 1645557742000 });
  const { nuevoId } = await cargarGenerador();
  const identificadores = Array.from({ length: 1000 }, () => nuevoId());
  for (let paso = 0; paso < 10; paso++) {
    contexto.mock.timers.tick(1);
    identificadores.push(nuevoId());
  }
  assert.equal(new Set(identificadores).size, identificadores.length);
  assert.deepEqual(identificadores, [...identificadores].sort());
  for (const identificador of identificadores) assert.match(identificador, formato);
  const milisegundos = (identificador) => Number.parseInt(identificador.replaceAll("-", "").slice(0, 12), 16);
  assert.equal(milisegundos(identificadores[0]), 1645557742000);
  assert.equal(milisegundos(identificadores.at(-1)), 1645557742010);
});

test("el acarreo mantiene la versión 7 y la variante 10", async (contexto) => {
  contexto.mock.timers.enable({ apis: ["Date"], now: 1645557742000 });
  fijarAleatorio(contexto, (1n << 62n) - 1n);
  const { nuevoId } = await cargarGenerador();
  assert.equal(nuevoId(), "017f22e2-79b0-7000-bfff-ffffffffffff");
  assert.equal(nuevoId(), "017f22e2-79b0-7001-8000-000000000000");
});

test("el agotamiento no repite UUID ni altera sus bits de formato", async (contexto) => {
  contexto.mock.timers.enable({ apis: ["Date"], now: 1645557742000 });
  fijarAleatorio(contexto, (1n << 74n) - 1n);
  const { nuevoId } = await cargarGenerador();
  const primero = nuevoId();
  assert.match(primero, formato);
  assert.throws(() => nuevoId(), RangeError);
  contexto.mock.timers.tick(1);
  assert.ok(nuevoId() > primero);
});

test("rechaza momentos fuera de los 48 bits del formato", async (contexto) => {
  contexto.mock.timers.enable({ apis: ["Date"], now: 0 });
  const { nuevoId } = await cargarGenerador();
  const lectura = contexto.mock.method(Date.prototype, "getTime", () => -1);
  assert.throws(() => nuevoId(), RangeError);
  lectura.mock.restore();
  contexto.mock.timers.setTime(2 ** 48);
  assert.throws(() => nuevoId(), RangeError);
});
