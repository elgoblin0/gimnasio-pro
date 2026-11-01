import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import * as textos from "./bandeja-textos.js";
import { crearControlDeOperacion } from "./comun/operaciones.js";

const codigoSalud = readFileSync(new URL("./salud.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replaceAll("export ", "");
const codigoBandeja = readFileSync(new URL("./bandeja.js", import.meta.url), "utf8")
  .replace(/^import[\s\S]*?;\r?\n/gm, "").replace(/iniciar\(\)\.catch\([\s\S]*$/, "");

function crear(etiqueta, propiedades = {}, ...hijos) {
  return {
    etiqueta, ...propiedades, hijos: hijos.flat().filter(Boolean), dataset: {}, eventos: {},
    append(...nuevos) { this.hijos.push(...nuevos.flat().filter(Boolean)); },
    replaceChildren(...nuevos) { this.hijos = nuevos; },
    addEventListener(nombre, funcion) { this.eventos[nombre] = funcion; },
  };
}

function preparar(llamarApi) {
  const elementos = new Map();
  const obtener = (selector) => {
    if (!elementos.has(selector)) elementos.set(selector, crear("section", { hidden: true }));
    return elementos.get(selector);
  };
  const contexto = vm.createContext({
    ...textos, crear, llamarApi, crearControlDeOperacion, registrarPwa() {}, montarPerfil() {},
    document: { querySelector: obtener }, ZONAS_CUERPO: [],
    formatearFechaHora: (fecha) => fecha, crypto: { randomUUID: () => "clave" },
    FormData: class { get() { return "Nota ficticia"; } },
  });
  vm.runInContext(codigoSalud + "\n" + codigoBandeja, contexto);
  return { contexto, obtener, ejecutar: (codigo) => vm.runInContext(codigo, contexto) };
}

const vista = (id) => ({ socio: { id }, avisos: [], sesiones_realizadas: [], salud: {}, sin_consentimiento: false });
const salud = () => ({ condiciones: [{ id: "condicion", descripcion: "Condición ficticia", registrada_en: "2026-11-01T12:00:00+00:00" }], restricciones: [], dolores: [] });
const terminarLecturas = () => new Promise((resolver) => setImmediate(resolver));

for (const momento of ["guardado", "recarga"]) {
  test(`cambiar de socio durante ${momento} de salud conserva la lectura de la ficha nueva`, async () => {
    let resolverGuardado, resolverRecarga, resolverSocio;
    let lecturasSalud = 0;
    const peticiones = [];
    const pantalla = preparar((ruta, opciones) => {
      peticiones.push(ruta);
      if (opciones) return new Promise((resolver) => { resolverGuardado = resolver; });
      if (ruta === "/api/entrenador/socios/nuevo") return new Promise((resolver) => { resolverSocio = resolver; });
      if (ruta === "/api/entrenador/socios/anterior") return vista("anterior");
      if (ruta === "/api/ejercicios") return { ejercicios: [] };
      if (ruta === "/api/socios/anterior/salud" && ++lecturasSalud > 1 && momento === "recarga") {
        return new Promise((resolver) => { resolverRecarga = resolver; });
      }
      return salud();
    });
    pantalla.ejecutar('mostrarSocio("anterior")');
    await terminarLecturas();
    const contenedor = pantalla.obtener("[data-salud]");
    const condicion = contenedor.hijos.find((hijo) => hijo.etiqueta === "article");
    const formulario = condicion.hijos.find((hijo) => hijo.etiqueta === "form");
    const guardado = formulario.eventos.submit({ preventDefault() {} });
    if (momento === "recarga") {
      resolverGuardado({});
      await terminarLecturas();
    }
    pantalla.ejecutar('mostrarSocio("nuevo")');
    const hijos = [...contenedor.hijos];
    if (momento === "guardado") resolverGuardado({});
    else resolverRecarga(salud());
    await guardado;
    assert.deepEqual(contenedor.hijos, hijos);
    resolverSocio(vista("nuevo"));
    await terminarLecturas();
    assert.equal(pantalla.obtener("[data-socio]").hidden, false);
    assert.equal(pantalla.obtener("[data-salud]").dataset.saludSocio.startsWith("nuevo:"), true);
    assert.equal(peticiones.filter((ruta) => ruta === "/api/entrenador/socios/anterior").length, 1);
  });
}

test("volver al mismo socio después de cerrar la ficha inicia una nueva presentación de salud", async () => {
  let lecturasSalud = 0;
  const pantalla = preparar((ruta) => {
    if (ruta === "/api/entrenador/socios/anterior") return vista("anterior");
    if (ruta === "/api/ejercicios") return { ejercicios: [] };
    lecturasSalud++;
    return salud();
  });
  pantalla.ejecutar('mostrarSocio("anterior")');
  await terminarLecturas();
  pantalla.ejecutar('mostrarSocio(null); mostrarSocio("anterior")');
  await terminarLecturas();
  assert.equal(lecturasSalud, 2);
});
