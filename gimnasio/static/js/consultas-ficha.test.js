import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./consultas-ficha.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replaceAll("export ", "");
function crear(etiqueta, propiedades = {}, ...hijos) {
  return {
    etiqueta, ...propiedades, hijos, eventos: {},
    replaceChildren(...nuevos) { this.hijos = nuevos; },
    append(...nuevos) { this.hijos.push(...nuevos); },
    addEventListener(nombre, funcion) { this.eventos[nombre] = funcion; },
    click() {}, remove() {},
  };
}
function entorno(llamarApi) {
  const resultado = vm.createContext({
    crear, llamarApi, formatearFechaHora: (fecha) => fecha, Blob,
    URL: { createObjectURL: () => "blob:datos", revokeObjectURL() {} }, setTimeout: (funcion) => funcion(),
  });
  vm.runInContext(codigo, resultado);
  return resultado;
}
const boton = (contenedor, texto) => contenedor.hijos.find((hijo) => hijo.etiqueta === "button" && hijo.hijos[0] === texto);

test("lista consultas con quién y cuándo, pagina y permite volver", async () => {
  const rutas = [];
  const contexto = entorno(async (ruta) => {
    rutas.push(ruta);
    const pagina = ruta.endsWith("=2") ? 2 : 1;
    return { pagina, hay_mas: pagina === 1, consultas: [{ nombre: "Nombre", apellido: "Ficticio", rol: "entrenador", registrada_en: "27/10/2026" }] };
  });
  const contenedor = crear("section");
  await contexto.montarConsultasFicha(contenedor);
  assert.equal(contenedor.hidden, false);
  assert.match(JSON.stringify(contenedor.hijos), /Nombre Ficticio · entrenador · 27\/10\/2026/);
  assert.equal(boton(contenedor, "Anterior").disabled, true);
  await boton(contenedor, "Siguiente").eventos.click();
  assert.equal(boton(contenedor, "Siguiente").disabled, true);
  await boton(contenedor, "Anterior").eventos.click();
  assert.deepEqual(rutas, ["/api/yo/salud/consultas?pagina=1", "/api/yo/salud/consultas?pagina=2", "/api/yo/salud/consultas?pagina=1"]);
});

test("muestra error, permite reintentar y muestra el estado vacío", async () => {
  let intentos = 0;
  const contexto = entorno(async () => {
    if (++intentos === 1) throw new Error("Sin conexión");
    return { pagina: 1, hay_mas: false, consultas: [] };
  });
  const contenedor = crear("section");
  await contexto.montarConsultasFicha(contenedor);
  assert.match(JSON.stringify(contenedor.hijos), /Sin conexión/);
  assert.equal(boton(contenedor, "Reintentar").hidden, false);
  await boton(contenedor, "Reintentar").eventos.click();
  assert.match(JSON.stringify(contenedor.hijos), /Todavía no hay consultas/);
  assert.equal(boton(contenedor, "Reintentar").hidden, true);
});

test("la descarga conserva el botón tras un error y genera el archivo al reintentar", async () => {
  let descargas = 0;
  const contexto = entorno(async (ruta) => {
    if (ruta === "/api/yo/datos") {
      if (++descargas === 1) throw new Error("Sin conexión");
      return { persona: [{ nombre: "Ficticio" }] };
    }
    return { pagina: 1, hay_mas: false, consultas: [] };
  });
  const contenedor = crear("section");
  await contexto.montarConsultasFicha(contenedor);
  const descarga = boton(contenedor, "Descargar mis datos");
  await descarga.eventos.click();
  assert.equal(descarga.disabled, false);
  assert.match(JSON.stringify(contenedor.hijos), /Sin conexión/);
  await descarga.eventos.click();
  assert.equal(descarga.disabled, false);
  assert.match(JSON.stringify(contenedor.hijos), /Datos descargados/);
  assert.equal(contenedor.hijos.find((hijo) => hijo.etiqueta === "a").download, "mis-datos.json");
});
