import test from "node:test";
import assert from "node:assert/strict";
import { crearControlDeOperacion, cerrarSesion } from "./operaciones.js";

test("el reintento conserva id, clave y cuerpo y bloquea un envío doble", () => {
  let cantidad = 0;
  const control = crearControlDeOperacion(() => String(++cantidad));
  const cuerpo = { socio_id: "socio", sede_id: "sede" };
  const primera = control.preparar("/api/entradas", cuerpo);
  cuerpo.socio_id = "otro";
  assert.equal(control.comenzar(), primera);
  assert.equal(control.comenzar(), null);
  assert.throws(() => control.descartar());
  control.finalizar({ estadoHttp: 0 });
  assert.equal(control.comenzar(), primera);
  assert.equal(primera.cuerpo.socio_id, "socio");
  assert.equal(cantidad, 2);
  control.finalizar();
  const nueva = control.preparar("/api/entradas", cuerpo);
  assert.notEqual(nueva.cuerpo.id, primera.cuerpo.id);
  assert.notEqual(nueva.clave, primera.clave);
});

test("una respuesta definitiva permite operación nueva y una incierta conserva la anterior", () => {
  const control = crearControlDeOperacion();
  const primera = control.preparar("/api/salidas", { entrada_id: "entrada" });
  control.comenzar();
  control.finalizar({ estadoHttp: 409, codigo: "solicitud_en_curso" });
  assert.equal(control.actual, primera);
  control.descartar();
  const nueva = control.preparar("/api/entradas", {});
  control.comenzar();
  control.finalizar({ estadoHttp: 409, codigo: "aforo_alcanzado" });
  assert.equal(control.actual, null);
  assert.notEqual(nueva, primera);
});

test("cerrar sesión solo elimina la sesión de usuario, nunca registra una salida", async () => {
  const llamadas = [];
  await cerrarSesion(async (...argumentos) => llamadas.push(argumentos));
  assert.deepEqual(llamadas, [["/api/sesion", { metodo: "DELETE" }]]);
});
