import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const codigo = readFileSync(new URL("./ficha.js", import.meta.url), "utf8")
  .split("async function montarPagos()")[1].split("async function montarConsentimiento")[0];

function crear(etiqueta, propiedades = {}, ...hijos) {
  return { etiqueta, ...propiedades, hijos,
    append(...nuevos) { this.hijos.push(...nuevos); },
    replaceChildren(...nuevos) { this.hijos = nuevos; },
  };
}

for (const vigente of [true, false]) {
  test(`Mi ficha presenta vigencia ${vigente} y pagos anulados en fecha de la sede`, async () => {
    const contenedor = crear("section");
    const contexto = vm.createContext({
      $: () => contenedor, crear, Intl, Date, formatearFecha: () => "30/10/2026", formatearGuaranies: () => "₲ 250.000",
      llamarApi: async (ruta) => {
        assert.equal(ruta, "/api/yo/pagos");
        return { membresia: { vigente, hasta: "2026-10-30", dias_restantes: 3 },
          pagos: [{ registrado_en: "2026-10-28T02:00:00+00:00", tipo: "Mensual", medio: "efectivo",
            monto: 250000, anulacion: { motivo: "Error ficticio" } }] };
      },
    });
    vm.runInContext(`async function montarPagos()${codigo}`, contexto);
    await contexto.montarPagos();
    assert.equal(contenedor.hidden, false);
    assert.match(contenedor.hijos[1].hijos[0], vigente ? /3 días restantes/ : /Sin membresía vigente/);
    assert.match(contenedor.hijos[2].hijos[0], /27\/10\/2026.*Mensual.*₲ 250.000.*Anulado: Error ficticio/);
  });
}

test("Mi ficha sin membresía ni pagos presenta el estado vacío", async () => {
  const contenedor = crear("section");
  const contexto = vm.createContext({
    $: () => contenedor, crear,
    llamarApi: async () => ({ membresia: { vigente: false }, pagos: [] }),
  });
  vm.runInContext(`async function montarPagos()${codigo}`, contexto);
  await contexto.montarPagos();
  assert.equal(contenedor.hijos.at(-1).hijos[0], "Todavía no tenés pagos registrados.");
});
