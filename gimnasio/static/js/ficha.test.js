import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./ficha.js", import.meta.url), "utf8")
  .split("async function montarConsentimiento")[1];

function crear(etiqueta, propiedades = {}, ...hijos) {
  return {
    etiqueta, ...propiedades, hijos, eventos: {},
    set textContent(texto) { this.hijos = [texto]; },
    replaceChildren(...nuevos) { this.hijos = nuevos; },
    addEventListener(nombre, funcion) { this.eventos[nombre] = funcion; },
  };
}

test("el consentimiento se actualiza con el POST aunque las lecturas posteriores fallen", async () => {
  const contenedor = crear("section");
  let lecturas = 0;
  const escrituras = [];
  const contexto = vm.createContext({
    $: () => contenedor, crear, window: { confirm: () => true },
    crypto: { randomUUID: () => `clave-${escrituras.length}` },
    llamarApi: async (ruta, opciones) => {
      if (!opciones) {
        if (++lecturas > 1) throw new Error("Sin conexión");
        return { salud: { otorgado: false, texto: "Texto vigente", version_texto: "salud-1" } };
      }
      escrituras.push(opciones);
      return { salud: { ...opciones.cuerpo, texto: "Texto vigente" } };
    },
  });
  vm.runInContext(`async function montarConsentimiento${codigo}`, contexto);
  await contexto.montarConsentimiento();
  await contenedor.hijos.find((hijo) => hijo.etiqueta === "button").eventos.click();
  let boton = contenedor.hijos.find((hijo) => hijo.etiqueta === "button");
  assert.ok(boton, "la sección conserva un botón visible");
  assert.deepEqual(boton.hijos, ["Revocar consentimiento de salud"]);
  assert.ok(!boton.disabled);
  await boton.eventos.click();
  boton = contenedor.hijos.find((hijo) => hijo.etiqueta === "button");
  assert.deepEqual(boton.hijos, ["Otorgar consentimiento de salud"]);
  assert.equal(lecturas, 1);
  assert.deepEqual(escrituras.map((opciones) => opciones.cuerpo.otorgado), [true, false]);
  assert.notEqual(escrituras[0].clave, escrituras[1].clave);
});

test("el borrado se ofrece solo con el consentimiento revocado y exige escribir BORRAR", async () => {
  const contenedor = crear("section");
  const escrituras = [];
  let fallar = true;
  const contexto = vm.createContext({
    $: () => contenedor, crear, window: { confirm: () => true },
    crypto: { randomUUID: () => "clave-borrado" },
    llamarApi: async (ruta, opciones) => {
      if (!opciones) return { salud: { otorgado: false, revocado: lecturaRevocada, texto: "Texto", version_texto: "salud-1" } };
      escrituras.push({ ruta, ...opciones });
      if (fallar) throw new Error("Sin conexión");
      return { borrado_salud_id: "x" };
    },
  });
  let lecturaRevocada = false;
  const formulario = () => contenedor.hijos.find((hijo) => hijo.etiqueta === "form");
  vm.runInContext(`async function montarConsentimiento${codigo}; globalThis.montar = montarConsentimiento`, contexto);
  await contexto.montar();
  assert.equal(formulario(), undefined, "sin revocación no hay borrado");
  lecturaRevocada = true;
  await contexto.montar();
  const forma = formulario();
  const campo = forma.hijos.find((hijo) => hijo.etiqueta === "label").hijos[1];
  const boton = forma.hijos.find((hijo) => hijo.etiqueta === "button");
  const enviar = () => forma.eventos.submit({ preventDefault() {} });
  assert.ok(boton.disabled);
  campo.value = "borrar";
  campo.eventos.input();
  assert.ok(boton.disabled);
  await enviar();
  assert.equal(escrituras.length, 0, "sin la palabra exacta no se envía");
  campo.value = "BORRAR";
  campo.eventos.input();
  assert.ok(!boton.disabled);
  await enviar();
  assert.ok(!boton.disabled, "un error permite reintentar");
  fallar = false;
  await enviar();
  assert.deepEqual(escrituras.map((e) => [e.ruta, e.clave, e.cuerpo.confirmacion]), [
    ["/api/yo/salud/borrar", "clave-borrado", "BORRAR"],
    ["/api/yo/salud/borrar", "clave-borrado", "BORRAR"],
  ]);
  assert.deepEqual(forma.hijos[0].hijos, ["Tus datos de salud se borraron."]);
});
