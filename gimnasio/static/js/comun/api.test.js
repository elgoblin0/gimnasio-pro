import assert from "node:assert/strict";
import test from "node:test";

import { crearApi, ErrorDeApi } from "./api.js";

function fetchFalso(estado, cuerpo) {
  const llamadas = [];
  const pedir = async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    return { ok: estado < 400, status: estado, json: async () => cuerpo };
  };
  return { pedir, llamadas };
}

test("un GET no lleva encabezados de cambio", async () => {
  const { pedir, llamadas } = fetchFalso(200, { estado: "ok" });
  const datos = await crearApi({ fetch: pedir })("/api/estado");
  assert.deepEqual(datos, { estado: "ok" });
  assert.equal(llamadas[0].opciones.headers["X-Gimnasio"], undefined);
  assert.equal(llamadas[0].opciones.headers["Idempotency-Key"], undefined);
  assert.equal(llamadas[0].opciones.cache, "no-store");
});

test("sin red falla con conexión requerida y no reintenta escrituras", async () => {
  let llamadas = 0;
  const llamar = crearApi({ fetch: async () => {
    llamadas += 1;
    throw new TypeError("Failed to fetch");
  }, nuevaClave: () => "clave-1" });
  await assert.rejects(llamar("/api/sesion", { metodo: "POST", cuerpo: {} }), (error) => {
    assert.ok(error instanceof ErrorDeApi);
    assert.equal(error.codigo, "conexion_requerida");
    assert.match(error.message, /Se requiere conexión/);
    assert.equal(error.estadoHttp, 0);
    return true;
  });
  assert.equal(llamadas, 1);
});

test("un POST lleva X-Gimnasio y una clave de idempotencia", async () => {
  const { pedir, llamadas } = fetchFalso(201, {});
  await crearApi({ fetch: pedir, nuevaClave: () => "clave-1" })("/api/x", { metodo: "POST", cuerpo: { a: 1 } });
  const { headers, body } = llamadas[0].opciones;
  assert.equal(headers["X-Gimnasio"], "1");
  assert.equal(headers["Idempotency-Key"], "clave-1");
  assert.equal(body, '{"a":1}');
});

test("un reintento puede reutilizar su clave", async () => {
  const { pedir, llamadas } = fetchFalso(201, {});
  await crearApi({ fetch: pedir })("/api/x", { metodo: "POST", cuerpo: {}, clave: "misma" });
  assert.equal(llamadas[0].opciones.headers["Idempotency-Key"], "misma");
});

test("un error de la API se convierte en ErrorDeApi con su código", async () => {
  const { pedir } = fetchFalso(422, { error: { codigo: "clave_reutilizada", mensaje: "Otro cuerpo" } });
  await assert.rejects(crearApi({ fetch: pedir })("/api/x", { metodo: "POST", cuerpo: {} }), (error) => {
    assert.ok(error instanceof ErrorDeApi);
    assert.equal(error.codigo, "clave_reutilizada");
    assert.equal(error.estadoHttp, 422);
    return true;
  });
});
