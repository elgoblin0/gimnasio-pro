import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import "./menu.js";

const { entradasDelMenu, dibujarMenu, leerSesion, sincronizarSesion } = globalThis.menuGimnasio;
const textos = (rol, ruta = "/") => entradasDelMenu(rol, ruta).map((entrada) => entrada.texto);
const activa = (rol, ruta) => entradasDelMenu(rol, ruta).filter((entrada) => entrada.actual)
  .map((entrada) => [entrada.texto, entrada.actual]);

function almacen(inicial = {}) {
  const datos = new Map(Object.entries(inicial));
  return {
    datos,
    getItem: (clave) => datos.get(clave) ?? null,
    setItem: (clave, valor) => datos.set(clave, valor),
    removeItem: (clave) => datos.delete(clave),
  };
}

test("cada rol tiene su menú único, en el mismo orden en cualquier pantalla", () => {
  assert.deepEqual(textos("socio"), ["Mi entrenamiento", "Mi progreso", "Clases", "Mi ficha"]);
  assert.deepEqual(textos("recepcion"), ["Recepción", "Pagos", "Clases"]);
  assert.deepEqual(textos("entrenador"), ["Bandeja", "Equipos", "Clases"]);
  assert.deepEqual(textos("administracion"), ["Administración", "Clases"]);
  assert.deepEqual(textos("socio", "/resumen-sesion.html"), textos("socio", "/clases.html"));
});

test("un rol desconocido no tiene entradas", () => {
  assert.deepEqual(textos("visitante"), []);
  assert.deepEqual(textos(undefined), []);
});

test("marca la pantalla propia con page y la incluida con true", () => {
  assert.deepEqual(activa("recepcion", "/pagos.html"), [["Pagos", "page"]]);
  assert.deepEqual(activa("socio", "/resumen-sesion.html"), [["Mi entrenamiento", "true"]]);
  assert.deepEqual(activa("socio", "/ficha.html"), [["Mi ficha", "page"]]);
  assert.deepEqual(activa("recepcion", "/ficha.html"), [["Recepción", "true"]]);
  assert.deepEqual(activa("entrenador", "/editor-programa.html"), [["Bandeja", "true"]]);
  for (const ruta of ["/pagos.html", "/equipos.html", "/plantillas.html", "/editor-programa.html"]) {
    assert.deepEqual(activa("administracion", ruta), [["Administración", "true"]]);
  }
  assert.deepEqual(activa("entrenador", "/equipos.html"), [["Equipos", "page"]]);
  assert.deepEqual(activa("administracion", "/clases.html"), [["Clases", "page"]]);
});

test("dibuja los enlaces con aria-current y reemplaza lo anterior", () => {
  const nav = {
    dataset: {},
    ownerDocument: {
      createElement: () => ({
        atributos: {},
        setAttribute(nombre, valor) { this.atributos[nombre] = valor; },
      }),
    },
    replaceChildren(...hijos) { this.hijos = hijos; },
  };
  dibujarMenu(nav, "recepcion", "/pagos.html");
  assert.equal(nav.dataset.rol, "recepcion");
  assert.deepEqual(nav.hijos.map((a) => [a.textContent, a.href, a.atributos["aria-current"]]), [
    ["Recepción", "/recepcion.html", undefined],
    ["Pagos", "/pagos.html", "page"],
    ["Clases", "/clases.html", undefined],
  ]);
});

test("recuerda rol y demo, olvida al cerrar sesión e ignora lo que no entiende", () => {
  const guardado = almacen();
  assert.equal(leerSesion(guardado), null);
  sincronizarSesion({ rol: "entrenador", es_demo: 1, nombre: "No se guarda" }, guardado);
  assert.deepEqual(leerSesion(guardado), { rol: "entrenador", demo: true });
  assert.ok(![...guardado.datos.values()].some((valor) => valor.includes("No se guarda")));
  sincronizarSesion(null, guardado);
  assert.equal(guardado.datos.size, 0);
  sincronizarSesion({ rol: "visitante" }, guardado);
  assert.equal(guardado.datos.size, 0);
  assert.equal(leerSesion(almacen({ "gimnasio-sesion-menu": "no es json" })), null);
  assert.equal(leerSesion(almacen({ "gimnasio-sesion-menu": '{"rol":"visitante"}' })), null);
});

test("sin almacenamiento disponible no falla", () => {
  const roto = { getItem() { throw new Error("bloqueado"); }, setItem() { throw new Error("bloqueado"); } };
  assert.equal(leerSesion(roto), null);
  assert.doesNotThrow(() => sincronizarSesion({ rol: "socio" }, roto));
});

test("toda pantalla con cabecera usa el menú único, sin enlaces escritos a mano", () => {
  const carpeta = new URL("../../", import.meta.url);
  const pantallas = readdirSync(carpeta).filter((archivo) => archivo.endsWith(".html"));
  const conCabecera = pantallas.filter((archivo) => readFileSync(new URL(archivo, carpeta), "utf8").includes('class="cabecera"'));
  assert.ok(conCabecera.includes("resumen-sesion.html"));
  assert.equal(conCabecera.length, 12);
  for (const archivo of conCabecera) {
    const [cabecera] = readFileSync(new URL(archivo, carpeta), "utf8").match(/<header class="cabecera">.*?<\/header>/s);
    assert.ok(cabecera.includes('<nav aria-label="Secciones"><script src="/js/comun/menu.js"></script></nav>'), archivo);
    assert.ok(cabecera.includes("data-cerrar"), archivo);
    assert.ok(!/<a [^>]*href="\/\w/.test(cabecera), archivo);
  }
});
