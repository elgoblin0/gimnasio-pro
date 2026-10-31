import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./perfil-entrenamiento.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replaceAll("export ", "");

function nodo(etiqueta, propiedades = {}, ...hijos) {
  return {
    etiqueta, ...propiedades, hijos: hijos.flat(), eventos: {},
    append(...nuevos) { this.hijos.push(...nuevos); },
    replaceChildren(...nuevos) { this.hijos = nuevos; },
    addEventListener(nombre, funcion) { this.eventos[nombre] = funcion; },
  };
}

function preparar(llamarApi) {
  const contexto = vm.createContext({
    llamarApi, crear: nodo,
    FormData: class { constructor(formulario) { return formulario; } },
  });
  vm.runInContext(codigo, contexto);
  return contexto;
}

test("los campos vacíos se borran y los números se envían como enteros", () => {
  const contexto = preparar();
  const datos = contexto.datosDelPerfil([
    ["objetivo", ""], ["experiencia", "inicial"], ["disponibilidad_semanal", "3"],
    ["tiempo_por_sesion", "60"], ["preferencias", "Por la mañana"],
  ]);
  assert.equal(datos.objetivo, null);
  assert.equal(datos.disponibilidad_semanal, 3);
  assert.equal(datos.tiempo_por_sesion, 60);
  assert.equal(datos.experiencia, "inicial");
});

test("una lectura demorada no mezcla perfiles de dos socios", async () => {
  let liberar;
  const contexto = preparar(async (ruta) => ruta === "anterior"
    ? new Promise((resolver) => { liberar = resolver; })
    : { perfil_entrenamiento: { objetivo: "Actual" } });
  const contenedor = nodo("section");
  const anterior = contexto.montarPerfil(contenedor, "anterior");
  await contexto.montarPerfil(contenedor, "actual");
  const hijosActuales = [...contenedor.hijos];
  liberar({ perfil_entrenamiento: { objetivo: "Anterior" } });
  await anterior;
  assert.deepEqual(contenedor.hijos, hijosActuales);
  const formulario = contenedor.hijos.find((hijo) => hijo.etiqueta === "form");
  assert.equal(formulario.hijos[1].hijos[1].value, "Actual");
});

test("un perfil sin contenido explica que todos los campos son opcionales", async () => {
  const contexto = preparar(async () => ({ perfil_entrenamiento: { objetivo: null } }));
  const contenedor = nodo("section");
  await contexto.montarPerfil(contenedor, "actual");
  assert.match(contenedor.hijos.find((hijo) => hijo.role === "status").textContent, /Todos los campos son opcionales/);
  const formulario = contenedor.hijos.find((hijo) => hijo.etiqueta === "form");
  assert.equal(formulario.hijos[0].hijos[0],
    "Usamos tu perfil para que tu entrenador arme tu programa. No escribas datos de salud acá: van en tu ficha de salud.");
});

test("un error permite reintentar la lectura del perfil", async () => {
  const contexto = preparar(async () => { throw new Error("Sin conexión"); });
  const contenedor = nodo("section");
  await contexto.montarPerfil(contenedor, "actual");
  assert.equal(contenedor.hijos.find((hijo) => hijo.role === "alert").textContent, "Sin conexión");
  assert.equal(typeof contenedor.hijos.find((hijo) => hijo.etiqueta === "button").eventos.click, "function");
});

test("experiencia toma su nombre de la etiqueta sin incluir las opciones", async () => {
  const contexto = preparar(async () => ({ perfil_entrenamiento: { experiencia: null } }));
  const contenedor = nodo("section");
  await contexto.montarPerfil(contenedor, "actual");
  const formulario = contenedor.hijos.find((hijo) => hijo.etiqueta === "form");
  const etiqueta = formulario.hijos.find((hijo) => hijo.etiqueta === "label"
    && hijo.hijos.some((entrada) => entrada.name === "experiencia"));
  const entrada = etiqueta.hijos.find((hijo) => hijo.name === "experiencia");
  const texto = etiqueta.hijos.find((hijo) => hijo.id && hijo.id === entrada["aria-labelledby"]);
  assert.ok(texto, "el nombre accesible debe apuntar solo al texto de la etiqueta");
  assert.deepEqual(texto.hijos, ["Experiencia"]);
  assert.deepEqual(entrada.hijos.map((opcion) => opcion.value), ["", "inicial", "intermedia", "avanzada"]);
});
