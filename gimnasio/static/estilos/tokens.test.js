import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const CSS = readFileSync(new URL("./tokens.css", import.meta.url), "utf8");

const SEMANTICOS = [
  "--superficie", "--superficie-elevada", "--texto", "--texto-suave", "--acento",
  "--exito", "--alerta", "--peligro", "--freno", "--foco",
];
const PRIMITIVOS = ["--color-", "--espacio-", "--radio-", "--fuente-", "--duracion-", "--curva-"];

// Devuelve los bloques de reglas como { media, selector, variables }. Alcanza para una hoja de tokens.
function bloques(css, media = "") {
  const resultado = [];
  const limpio = css.replace(/\/\*[\s\S]*?\*\//g, "");
  let i = 0;
  while (i < limpio.length) {
    const apertura = limpio.indexOf("{", i);
    if (apertura === -1) break;
    const cabecera = limpio.slice(i, apertura).trim();
    let profundidad = 1;
    let fin = apertura + 1;
    while (profundidad > 0) {
      if (limpio[fin] === "{") profundidad += 1;
      if (limpio[fin] === "}") profundidad -= 1;
      fin += 1;
    }
    const cuerpo = limpio.slice(apertura + 1, fin - 1);
    if (cabecera.startsWith("@media")) {
      resultado.push(...bloques(cuerpo, cabecera));
    } else {
      const variables = {};
      for (const [, nombre, valor] of cuerpo.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) variables[nombre] = valor.trim();
      resultado.push({ media, selector: cabecera, variables });
    }
    i = fin;
  }
  return resultado;
}

const TODOS = bloques(CSS);
const bloque = (selector, media = "") => TODOS.find((b) => b.selector === selector && b.media === media);
const A = bloque('[data-direccion="a"]');
const B = bloque('[data-direccion="b"]');
const B_OSCURO = bloque('[data-direccion="b"]', "@media (prefers-color-scheme: dark)");

function resolver(variables, nombre) {
  let valor = variables[nombre];
  for (let vueltas = 0; valor?.startsWith("var("); vueltas += 1) {
    assert.ok(vueltas < 10, `referencia circular en ${nombre}`);
    valor = variables[valor.slice(4, -1).trim()];
  }
  assert.ok(valor, `falta ${nombre}`);
  return valor;
}

function aRgba(valor) {
  const hex = valor.match(/^#([\da-f]{6})$/i);
  if (hex) return [0, 2, 4].map((k) => parseInt(hex[1].slice(k, k + 2), 16)).concat(1);
  const rgb = valor.match(/^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:\/\s*([\d.]+))?\s*\)$/);
  assert.ok(rgb, `color no reconocido: ${valor}`);
  return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3]), rgb[4] === undefined ? 1 : Number(rgb[4])];
}

// Un color translúcido se compone sobre el fondo antes de medir.
function componer([r, g, b, alfa], fondo) {
  return [r, g, b].map((canal, k) => canal * alfa + fondo[k] * (1 - alfa));
}

function luminancia(rgb) {
  const [r, g, b] = rgb.map((canal) => {
    const c = canal / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contraste(variables, texto, fondo) {
  const superficie = componer(aRgba(resolver(variables, "--superficie")), [255, 255, 255]);
  const fondoReal = componer(aRgba(resolver(variables, fondo)), superficie);
  const textoReal = componer(aRgba(resolver(variables, texto)), fondoReal);
  const [claro, oscuro] = [luminancia(textoReal), luminancia(fondoReal)].sort((x, y) => y - x);
  return (claro + 0.05) / (oscuro + 0.05);
}

test("las dos direcciones definen el mismo conjunto de tokens semánticos", () => {
  const semanticos = (b) => Object.keys(b.variables).filter((n) => !PRIMITIVOS.some((p) => n.startsWith(p))).sort();
  assert.deepEqual(semanticos(A), semanticos(B));
  for (const nombre of SEMANTICOS) assert.ok(nombre in A.variables && nombre in B.variables, nombre);
});

test("las dos direcciones definen las mismas familias de primitivos no cromáticos", () => {
  const familias = (b) => Object.keys(b.variables).filter((n) => PRIMITIVOS.some((p) => n.startsWith(p)) && !n.startsWith("--color-")).sort();
  assert.deepEqual(familias(A), familias(B));
});

test("el modo oscuro de B solo cambia tokens semánticos existentes", () => {
  for (const nombre of Object.keys(B_OSCURO.variables)) {
    assert.ok(SEMANTICOS.includes(nombre) || nombre === "--borde", nombre);
  }
});

test("con movimiento reducido todas las duraciones valen 0ms", () => {
  const reducido = bloque("[data-direccion]", "@media (prefers-reduced-motion: reduce)");
  const duraciones = Object.keys(A.variables).filter((n) => n.startsWith("--duracion-"));
  assert.ok(duraciones.length > 0);
  for (const nombre of duraciones) assert.equal(reducido.variables[nombre], "0ms", nombre);
});

test("los pares de texto y superficie cumplen el contraste AA", () => {
  const esquemas = {
    a: A.variables,
    "b claro": B.variables,
    "b oscuro": { ...B.variables, ...B_OSCURO.variables },
  };
  for (const [esquema, variables] of Object.entries(esquemas)) {
    for (const texto of ["--texto", "--texto-suave"]) {
      for (const fondo of ["--superficie", "--superficie-elevada"]) {
        const valor = contraste(variables, texto, fondo);
        assert.ok(valor >= 4.5, `${esquema}: ${texto} sobre ${fondo} da ${valor.toFixed(2)}:1`);
      }
    }
  }
});

test("la función de contraste reproduce los valores de referencia de WCAG", () => {
  const variables = { "--superficie": "#ffffff", "--negro": "#000000", "--gris": "#767676" };
  assert.equal(contraste(variables, "--negro", "--superficie").toFixed(1), "21.0");
  assert.equal(contraste(variables, "--gris", "--superficie").toFixed(2), "4.54");
});
