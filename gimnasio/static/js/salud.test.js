import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./salud.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "").replace("export async function", "async function");
const vacia = () => ({ condiciones: [], restricciones: [], dolores: [] });
function crear(etiqueta, propiedades = {}, ...hijos) {
  return {
    etiqueta, ...propiedades, hijos: hijos.flat().filter(Boolean), eventos: {},
    append(...nuevos) { this.hijos.push(...nuevos.flat().filter(Boolean)); },
    replaceChildren(...nuevos) { this.hijos = nuevos; },
    addEventListener(nombre, funcion) { this.eventos[nombre] = funcion; },
  };
}
function contexto(llamarApi) {
  let ids = 0;
  const resultado = vm.createContext({
    crear, llamarApi, nuevoId: () => `id-${++ids}`, crypto: { randomUUID: () => `clave-${++ids}` },
    formatearFechaHora: (fecha) => fecha, ZONAS_CUERPO: [],
    FormData: class { get() { return "Condición ficticia"; } },
  });
  vm.runInContext(codigo, resultado);
  return resultado;
}

test("declarar conserva identificador, cuerpo y clave al reintentar sin conexión", async () => {
  const escrituras = [];
  const contenedor = crear("section");
  const entorno = contexto(async (ruta, opciones) => {
    if (!opciones) return vacia();
    escrituras.push({ ruta, ...opciones });
    if (escrituras.length === 1) throw new Error("Sin conexión");
    return {};
  });
  await entorno.montarSalud(contenedor);
  const forma = contenedor.hijos.find((hijo) => hijo.etiqueta === "form");
  const boton = forma.hijos.find((hijo) => hijo.etiqueta === "button");
  await forma.eventos.submit({ preventDefault() {} });
  assert.equal(boton.disabled, false);
  await forma.eventos.submit({ preventDefault() {} });
  assert.equal(escrituras[0].ruta, "/api/yo/salud/condiciones");
  assert.deepEqual(escrituras[0], escrituras[1]);
  assert.equal(escrituras[0].cuerpo.descripcion, "Condición ficticia");
});

test("una lectura anterior no vuelve a mostrar salud después de revocar", async () => {
  let resolver;
  let llamadas = 0;
  const entorno = contexto(() => {
    if (++llamadas === 1) return new Promise((resuelto) => { resolver = resuelto; });
    throw new Error("Se necesita consentimiento de salud vigente.");
  });
  const contenedor = crear("section");
  const anterior = entorno.montarSalud(contenedor);
  await entorno.montarSalud(contenedor);
  resolver(vacia());
  await anterior;
  assert.equal(contenedor.hijos.find((hijo) => hijo.role === "alert").hijos[0], "Se necesita consentimiento de salud vigente.");
  assert.ok(!contenedor.hijos.some((hijo) => hijo.etiqueta === "form"));
});
