import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./salud.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "").replaceAll("export ", "");
const vacia = () => ({ condiciones: [], restricciones: [], dolores: [] });

test("el entrenador escribe el aviso con límite, finalidad y clave de reintento", async () => {
  const escrituras = [];
  const entorno = contexto(async (ruta, opciones) => {
    if (opciones) { escrituras.push({ ruta, ...opciones }); throw new Error("Sin conexión"); }
    return ruta === "/api/ejercicios" ? { ejercicios: [] } : { ...vacia(), aviso_personal: "Consultar al entrenador" };
  });
  const contenedor = crear("section");
  await entorno.montarSalud(contenedor, "socio");
  const forma = contenedor.hijos.find((hijo) => hijo.etiqueta === "form");
  assert.equal(forma.hijos[0].hijos[0], "Lo lee recepción. No incluyas detalles de salud.");
  const campo = forma.hijos.find((hijo) => hijo.etiqueta === "label").hijos[1];
  assert.equal(campo.maxLength, 200);
  assert.equal(campo.value, "Consultar al entrenador");
  await forma.eventos.submit({ preventDefault() {} });
  await forma.eventos.submit({ preventDefault() {} });
  assert.equal(escrituras[0].ruta, "/api/socios/socio/aviso-personal");
  assert.equal(escrituras[0].cuerpo.texto, "Condición ficticia");
  assert.deepEqual(escrituras[0], escrituras[1]);
});
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

test("Mi ficha muestra el nombre del ejercicio restringido sin consultar el catálogo", async () => {
  const rutas = [];
  const entorno = contexto(async (ruta) => {
    rutas.push(ruta);
    return { ...vacia(), restricciones: [{ ejercicio_id: "ejercicio", ejercicio_nombre: "Sentadilla ficticia", descripcion: "No realizar con carga" }] };
  });
  const contenedor = crear("section");
  await entorno.montarSalud(contenedor);
  const restriccion = contenedor.hijos.find((hijo) => hijo.etiqueta === "article");
  assert.equal(restriccion.hijos[0].hijos[0], "Sentadilla ficticia: No realizar con carga");
  assert.deepEqual(rutas, ["/api/yo/salud"]);
});

test("invalidar la presentación impide que una lectura pendiente dibuje la salud del socio anterior", async () => {
  let resolver;
  const entorno = contexto((ruta) => ruta === "/api/ejercicios" ? { ejercicios: [] }
    : new Promise((resuelto) => { resolver = resuelto; }));
  const contenedor = crear("section");
  const lectura = entorno.montarSalud(contenedor, "anterior");
  entorno.invalidarSalud(contenedor);
  const hijos = [...contenedor.hijos];
  resolver(vacia());
  await lectura;
  assert.deepEqual(contenedor.hijos, hijos);
});
