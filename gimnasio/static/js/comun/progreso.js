// Geometría pura: las fechas determinan la escala horizontal, las cargas la vertical.
// El eje va de la carga más baja a la más alta, con aire: desde 0, un cambio de 20 a 28 kg casi no se vería.
export function escalaDeCargas(cargas) {
  if (!cargas.length) return { minima: 0, maxima: 1 };
  const baja = Math.min(...cargas);
  const alta = Math.max(...cargas);
  const aire = Math.max((alta - baja) * .15, alta * .05, .5);
  return { minima: Math.max(0, baja - aire), maxima: alta + aire };
}

export function calcularProgreso(puntos, { ancho, alto }) {
  const margen = { izquierda: 52, derecha: 20, arriba: 20, abajo: 40 };
  const fechas = puntos.map((p) => Date.parse(`${p.fecha_local}T00:00:00Z`));
  const inicio = Math.min(...fechas);
  const fin = Math.max(...fechas);
  const { minima, maxima } = escalaDeCargas(puntos.map((p) => Number(p.carga)));
  const izquierda = margen.izquierda;
  const derecha = Math.max(izquierda + 1, ancho - margen.derecha);
  const arriba = margen.arriba;
  const abajo = Math.max(arriba + 1, alto - margen.abajo);
  const marcas = puntos.map((p, i) => ({ ...p,
    x: fin === inicio ? (izquierda + derecha) / 2 : izquierda + (fechas[i] - inicio) / (fin - inicio) * (derecha - izquierda),
    y: abajo - (Number(p.carga) - minima) / (maxima - minima) * (abajo - arriba),
  }));
  return { ancho, alto, marcas,
    trazo: marcas.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" "),
    escalas: { izquierda, derecha, arriba, abajo, minima, maxima, inicio: puntos.length ? inicio : null, fin: puntos.length ? fin : null },
  };
}

// Lo que se lee primero: la carga de hoy y cuánto cambió desde el primer registro.
export function resumirProgreso(puntos) {
  if (!puntos.length) return null;
  const primera = Number(puntos[0].carga);
  const ultima = Number(puntos.at(-1).carga);
  return { ultima, cambio: ultima - primera, sesiones: puntos.length };
}
