import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./inicio.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replace(/iniciar\(\)\.catch\([\s\S]*$/, "");

function preparar(pedir) {
  const elementos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, {
      textContent: "", hijos: [],
      replaceChildren(...hijos) { this.hijos = hijos; },
    });
    return elementos.get(selector);
  };
  let clave = 0;
  const contexto = vm.createContext({
    document: { querySelector: obtener }, registrarPwa() {},
    crypto: { randomUUID: () => `clave-${++clave}` },
    llamarApi: pedir,
    crear: (etiqueta, propiedades, ...hijos) => ({ etiqueta, ...propiedades, hijos }),
  });
  vm.runInContext(codigo, contexto);
  return { obtener, cargar: () => vm.runInContext("cargarAvisos()", contexto) };
}

test("inicio sin avisos muestra el estado vacío", async () => {
  const pantalla = preparar(async () => ({ avisos: [] }));
  await pantalla.cargar();
  assert.equal(pantalla.obtener("[data-avisos-estado]").textContent, "No tenés avisos sin ver.");
  assert.equal(pantalla.obtener("[data-avisos-lista]").hijos.length, 0);
});

test("aviso muestra clase y fecha local; marcar como visto reintenta la misma clave", async () => {
  const envios = [];
  let visto = false;
  const pantalla = preparar(async (ruta, opciones) => {
    if (!opciones) return { avisos: visto ? [] : [{
      id: "aviso", tipo: "ocurrencia_cancelada", clase: "Clase ficticia",
      fecha: "2026-10-27", hora_inicio: "18:00",
    }] };
    envios.push({ ruta, clave: opciones.clave });
    if (envios.length === 1) throw new Error("Sin conexión");
    visto = true;
  });
  await pantalla.cargar();
  const fila = pantalla.obtener("[data-avisos-lista]").hijos[0];
  assert.match(fila.hijos[0], /Se canceló la ocurrencia · Clase ficticia · 27\/10\/2026 18:00/);
  const boton = fila.hijos[1];
  await boton.onclick();
  assert.equal(boton.disabled, false);
  assert.equal(pantalla.obtener("[data-avisos-estado]").textContent, "Sin conexión");
  await boton.onclick();
  assert.deepEqual(envios[0], envios[1]);
  assert.equal(envios[0].ruta, "/api/yo/avisos/aviso/visto");
  assert.equal(pantalla.obtener("[data-avisos-lista]").hijos.length, 0);
});

test("inicio permite reintentar una consulta fallida", async () => {
  let fallo = true;
  const pantalla = preparar(async () => {
    if (fallo) throw new Error("No se pudo conectar");
    return { avisos: [] };
  });
  await pantalla.cargar();
  assert.equal(pantalla.obtener("[data-avisos-estado]").textContent, "No se pudo conectar");
  fallo = false;
  await pantalla.cargar();
  assert.equal(pantalla.obtener("[data-avisos-estado]").textContent, "No tenés avisos sin ver.");
});
