// Geometría pura: las fechas determinan la escala horizontal, las cargas la vertical.
export function calcularProgreso(puntos, { ancho, alto }) {
  const margen = { izquierda: 52, derecha: 20, arriba: 20, abajo: 40 };
  const fechas = puntos.map((p) => Date.parse(`${p.fecha_local}T00:00:00Z`));
  const inicio = Math.min(...fechas);
  const fin = Math.max(...fechas);
  const maxima = Math.max(1, ...puntos.map((p) => Number(p.carga)));
  const izquierda = margen.izquierda;
  const derecha = Math.max(izquierda + 1, ancho - margen.derecha);
  const arriba = margen.arriba;
  const abajo = Math.max(arriba + 1, alto - margen.abajo);
  const marcas = puntos.map((p, i) => ({ ...p,
    x: fin === inicio ? (izquierda + derecha) / 2 : izquierda + (fechas[i] - inicio) / (fin - inicio) * (derecha - izquierda),
    y: abajo - Number(p.carga) / maxima * (abajo - arriba),
  }));
  return { ancho, alto, marcas,
    trazo: marcas.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" "),
    escalas: { izquierda, derecha, arriba, abajo, maxima, inicio: puntos.length ? inicio : null, fin: puntos.length ? fin : null },
  };
}
