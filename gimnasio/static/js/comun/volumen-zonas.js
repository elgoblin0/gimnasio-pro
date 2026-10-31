import { ZONAS_CUERPO } from "./zonas.js";

// Series semanales por zona del cuerpo. Sin juicios: la escala es relativa al máximo del propio programa.

/** Cada serie cuenta completa en todas las zonas del ejercicio. */
export function calcularVolumenPorZona(sesiones, zonasDeEjercicio) {
  const volumen = new Map();
  for (const sesion of sesiones) {
    for (const ejercicio of sesion.ejercicios) {
      const series = Number(ejercicio.series);
      if (!Number.isFinite(series) || series <= 0) continue;
      for (const zona of new Set(zonasDeEjercicio(ejercicio.ejercicio_id))) volumen.set(zona, (volumen.get(zona) ?? 0) + series);
    }
  }
  return volumen;
}

/** De 0 a 1 respecto de la zona más trabajada; sin trabajo, todo en cero. */
export function escalaRelativa(volumen) {
  const maximo = Math.max(0, ...volumen.values());
  return new Map([...volumen].map(([zona, series]) => [zona, maximo ? series / maximo : 0]));
}

export function totalDeSeries(sesiones) {
  return sesiones.reduce((total, sesion) => total + sesion.ejercicios.reduce((suma, ejercicio) => {
    const series = Number(ejercicio.series);
    return suma + (Number.isFinite(series) && series > 0 ? series : 0);
  }, 0), 0);
}

/** Filas para la alternativa sin 3D, de la zona más trabajada a la menos; las zonas sin series quedan al final. */
export function filasDeVolumen(volumen) {
  const relativa = escalaRelativa(volumen);
  return ZONAS_CUERPO
    .map((zona, indice) => ({ id: zona.id, nombre: zona.nombre, indice, series: volumen.get(zona.id) ?? 0, relativa: relativa.get(zona.id) ?? 0 }))
    .sort((a, b) => b.series - a.series || a.indice - b.indice);
}

/** Baja los rótulos que se pisan hasta que cada uno se lea. `arriba` es el centro vertical del rótulo. */
export function separarRotulos(rotulos, margen = 4) {
  const ubicados = [];
  for (const rotulo of [...rotulos].sort((a, b) => a.arriba - b.arriba)) {
    let arriba = rotulo.arriba;
    for (const otro of ubicados) {
      const seCruzan = rotulo.izquierda < otro.izquierda + otro.ancho && otro.izquierda < rotulo.izquierda + rotulo.ancho;
      const minimo = (rotulo.alto + otro.alto) / 2 + margen;
      if (seCruzan && Math.abs(arriba - otro.arriba) < minimo) arriba = otro.arriba + minimo;
    }
    const ubicado = { ...rotulo, arriba };
    ubicados.push(ubicado);
    ubicados.sort((a, b) => a.arriba - b.arriba);
  }
  return ubicados;
}
