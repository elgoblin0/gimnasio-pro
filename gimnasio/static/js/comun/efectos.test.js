import { test } from "node:test";
import assert from "node:assert/strict";
import { decidirModoSinEfectos, esDibujoPorSoftware, modoSinEfectos } from "./efectos.js";

const GPU = () => ({ webgl2: true, renderizador: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11)" });
const equipo = { nucleos: 8, memoria: 8, grafica: GPU };

test("un equipo con GPU y sin preferencias ve los efectos", () => {
  assert.deepEqual(decidirModoSinEfectos(equipo), { activo: false, motivo: null });
});

test("cada señal de detección activa el modo con su motivo", () => {
  assert.deepEqual(decidirModoSinEfectos({ ...equipo, movimientoReducido: true }), { activo: true, motivo: "movimiento-reducido" });
  assert.deepEqual(decidirModoSinEfectos({ ...equipo, nucleos: 2 }), { activo: true, motivo: "equipo-lento" });
  assert.deepEqual(decidirModoSinEfectos({ ...equipo, memoria: 1 }), { activo: true, motivo: "equipo-lento" });
  assert.deepEqual(decidirModoSinEfectos({ ...equipo, grafica: () => ({ webgl2: false, renderizador: "" }) }),
    { activo: true, motivo: "sin-webgl" });
  assert.deepEqual(decidirModoSinEfectos({ ...equipo, grafica: () => ({ webgl2: true, renderizador: "llvmpipe (LLVM 15.0.7)" }) }),
    { activo: true, motivo: "software" });
});

test("sin datos de núcleos ni memoria no se supone un equipo lento", () => {
  assert.equal(decidirModoSinEfectos({ grafica: GPU }).activo, false);
});

test("la elección manual manda sobre toda la detección", () => {
  const todoEnContra = { movimientoReducido: true, nucleos: 1, memoria: .5, grafica: () => ({ webgl2: false, renderizador: "" }) };
  assert.deepEqual(decidirModoSinEfectos({ ...todoEnContra, eleccion: "no" }), { activo: false, motivo: "eleccion" });
  assert.deepEqual(decidirModoSinEfectos({ ...equipo, eleccion: "si" }), { activo: true, motivo: "eleccion" });
});

test("WebGL solo se prueba si nada anterior decide", () => {
  let pruebas = 0;
  const grafica = () => { pruebas++; return GPU(); };
  decidirModoSinEfectos({ eleccion: "si", grafica });
  decidirModoSinEfectos({ movimientoReducido: true, grafica });
  decidirModoSinEfectos({ nucleos: 2, grafica });
  assert.equal(pruebas, 0);
  decidirModoSinEfectos({ grafica });
  assert.equal(pruebas, 1);
});

test("reconoce el dibujo por software", () => {
  assert.equal(esDibujoPorSoftware("ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)"), true);
  assert.equal(esDibujoPorSoftware("ANGLE (Microsoft, Microsoft Basic Render Driver Direct3D11)"), true);
  assert.equal(esDibujoPorSoftware("ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11)"), false);
  assert.equal(esDibujoPorSoftware(undefined), false);
});

test("un almacenamiento bloqueado no rompe la lectura y se decide por detección", () => {
  const documento = {
    defaultView: {
      get localStorage() { throw new Error("bloqueado"); },
      matchMedia: () => ({ matches: true }),
      navigator: {},
    },
  };
  assert.deepEqual(modoSinEfectos(documento), { activo: true, motivo: "movimiento-reducido" });
});

test("lee la elección guardada en el navegador", () => {
  const documento = {
    defaultView: {
      localStorage: { getItem: () => "no" },
      matchMedia: () => ({ matches: true }),
      navigator: {},
    },
  };
  assert.deepEqual(modoSinEfectos(documento), { activo: false, motivo: "eleccion" });
});
