import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";

const CODIGO = readFileSync(new URL("../../sw.js", import.meta.url), "utf8");
const ORIGEN = "https://gimnasio.example";

function entorno({ version = "1", almacen = new Map() } = {}) {
  const gestores = {};
  const solicitudesDeRed = [];
  let sinRed = false;
  let controlado = false;
  const caches = {
    keys: async () => [...almacen.keys()],
    delete: async (nombre) => almacen.delete(nombre),
    open: async (nombre) => {
      if (!almacen.has(nombre)) almacen.set(nombre, new Map());
      const entradas = almacen.get(nombre);
      return {
        addAll: async (solicitudes) => {
          for (const solicitud of solicitudes) {
            assert.equal(solicitud.credentials, "omit");
            assert.equal(solicitud.cache, "reload");
            assert.ok(!solicitud.url.includes("/api/"));
            entradas.set(solicitud.url, new Response("estático"));
          }
        },
        match: async (solicitud) => entradas.get(solicitud.url)?.clone(),
      };
    },
  };
  class Peticion extends Request {
    constructor(ruta, opciones) { super(new URL(ruta, ORIGEN), opciones); }
  }
  runInNewContext(CODIGO.replace(/const VERSION = "[^"]+";/, `const VERSION = "${version}";`), {
    self: {
      location: { origin: ORIGEN },
      clients: { claim: async () => { controlado = true; } },
      addEventListener: (evento, gestor) => { gestores[evento] = gestor; },
    },
    caches, Request: Peticion, Response, URL,
    fetch: async (solicitud, opciones) => {
      solicitudesDeRed.push({ solicitud, opciones });
      if (sinRed) throw new TypeError("Sin red");
      return new Response("red");
    },
  });
  return {
    almacen, solicitudesDeRed,
    cortarRed: () => { sinRed = true; },
    recuperarRed: () => { sinRed = false; },
    controlado: () => controlado,
    ciclo: (evento) => {
      let promesa;
      gestores[evento]({ waitUntil: (tarea) => { promesa = tarea; } });
      return promesa;
    },
    pedir: (ruta, method = "GET", mode = "cors") => {
      let promesa;
      gestores.fetch({
        request: { url: new URL(ruta, ORIGEN).href, method, mode },
        respondWith: (respuesta) => { promesa = respuesta; },
      });
      return promesa;
    },
  };
}

test("instala solo estáticos públicos y la activación purga solo versiones propias anteriores", async () => {
  const inicial = entorno();
  await inicial.ciclo("install");
  await inicial.ciclo("activate");
  assert.ok(inicial.controlado());
  assert.ok(inicial.almacen.get("gimnasio-estaticos-1").size > 0);
  assert.ok([...inicial.almacen.get("gimnasio-estaticos-1").keys()].every((ruta) =>
    /\.(css|js|png|webmanifest)$/.test(ruta) && !ruta.endsWith("sw.js")));
  inicial.almacen.set("otra-aplicacion", new Map());
  const siguiente = entorno({ version: "2", almacen: inicial.almacen });
  await siguiente.ciclo("install");
  assert.ok(siguiente.almacen.has("gimnasio-estaticos-1"));
  await siguiente.ciclo("activate");
  assert.deepEqual([...siguiente.almacen.keys()].sort(), ["gimnasio-estaticos-2", "otra-aplicacion"]);
});

test("solo una petición GET exacta de la lista usa caché", async () => {
  const sw = entorno();
  await sw.ciclo("install");
  assert.equal(await (await sw.pedir("/js/inicio.js")).text(), "estático");
  assert.equal(sw.solicitudesDeRed.length, 0);
  for (const ruta of ["/", "/index.html", "/api/sesion", "/js/inicio.js?otro=1", "https://otro.example/js/inicio.js"]) {
    assert.equal(await (await sw.pedir(ruta)).text(), "red");
  }
  assert.equal(await (await sw.pedir("/js/inicio.js", "POST")).text(), "red");
  assert.equal(await (await sw.pedir("/js/inicio.js", "HEAD")).text(), "red");
  assert.equal(sw.solicitudesDeRed.length, 7);
  assert.ok(sw.solicitudesDeRed.every(({ opciones }) => opciones.cache === "no-store"));
  assert.ok(!sw.almacen.get("gimnasio-estaticos-1").has(ORIGEN + "/api/sesion"));
});

test("API y escrituras fallan sin red y recuperarla no provoca reenvíos", async () => {
  const sw = entorno();
  await sw.ciclo("install");
  const inicial = [...sw.almacen.get("gimnasio-estaticos-1").keys()];
  sw.cortarRed();
  for (const metodo of ["GET", "POST", "PUT", "PATCH", "DELETE"]) {
    await assert.rejects(sw.pedir("/api/sesion", metodo), /Sin red/);
  }
  sw.recuperarRed();
  await sw.pedir("/api/estado");
  assert.equal(sw.solicitudesDeRed.length, 6);
  assert.deepEqual([...sw.almacen.get("gimnasio-estaticos-1").keys()], inicial);
});

test("navegar sin red muestra conexión requerida con 503 y no guarda HTML", async () => {
  const sw = entorno();
  await sw.ciclo("install");
  sw.cortarRed();
  const respuesta = await sw.pedir("/", "GET", "navigate");
  assert.equal(respuesta.status, 503);
  assert.match(respuesta.headers.get("Content-Type"), /text\/html/);
  assert.match(await respuesta.text(), /Conexión requerida/);
  assert.equal(respuesta.headers.get("Cache-Control"), "no-store");
  assert.ok(!sw.almacen.get("gimnasio-estaticos-1").has(ORIGEN + "/"));
});
