// Semana tipo del editor, sin DOM ni API. Los campos guardan texto: es lo que hay en el formulario.

export const LIMITES = Object.freeze({ sesiones: [1, 6], ejercicios: [1, 12], series: [1, 10], semanas: [4, 12] });
export const SEMANAS_POR_DEFECTO = 8;

const CAMPOS = ["series", "repeticiones_minimas", "repeticiones_maximas", "rir_objetivo", "descanso", "carga", "carga_partida", "duracion", "distancia"];
const ENTEROS = new Set(["series", "repeticiones_minimas", "repeticiones_maximas", "rir_objetivo", "descanso", "duracion"]);
const POR_MEDIDA = { repeticiones: ["repeticiones_minimas", "repeticiones_maximas"], carga: ["carga", "carga_partida"], duracion: ["duracion"], distancia: ["distancia"] };
const VALORES_NUEVOS = { series: 3, repeticiones_minimas: 8, repeticiones_maximas: 12, rir_objetivo: 2, descanso: 90, duracion: 600, distancia: 1000 };

const comoTexto = (valor) => (valor === null || valor === undefined ? "" : String(valor));

function fila(origen) {
  const resultado = { ejercicio_id: origen.ejercicio_id };
  for (const campo of CAMPOS) resultado[campo] = comoTexto(origen[campo]);
  return resultado;
}

export const filaNueva = (ejercicio) => fila({
  ejercicio_id: ejercicio.id,
  ...Object.fromEntries(Object.entries(VALORES_NUEVOS).filter(([campo]) => campoAplica(campo, ejercicio))),
  series: VALORES_NUEVOS.series,
  rir_objetivo: VALORES_NUEVOS.rir_objetivo,
  descanso: VALORES_NUEVOS.descanso,
});

export function campoAplica(campo, ejercicio) {
  if (["series", "rir_objetivo", "descanso"].includes(campo)) return true;
  return (ejercicio?.medidas_aplicables ?? []).some((medida) => POR_MEDIDA[medida]?.includes(campo));
}

/** Una plantilla no trae carga: la fija el entrenador o sale de la sugerida. */
export function semanaDesdePlantilla(plantilla) {
  return {
    semanas: String(SEMANAS_POR_DEFECTO),
    sesiones: plantilla.sesiones.map((sesion) => ({ nombre: sesion.nombre, ejercicios: sesion.ejercicios.map(fila) })),
  };
}

/** La carga de partida de la versión vigente no se hereda: ya cumplió su función y volvería a bajar la carga. */
export function semanaDesdeVigente(programa) {
  return {
    semanas: String(programa.duracion_semanas ?? SEMANAS_POR_DEFECTO),
    sesiones: programa.sesiones.map((sesion) => ({
      nombre: sesion.nombre,
      ejercicios: sesion.ejercicios.map((ejercicio) => ({ ...fila(ejercicio), carga_partida: "" })),
    })),
  };
}

export const semanaVacia = () => ({ semanas: String(SEMANAS_POR_DEFECTO), sesiones: [] });

export function ajustarSeries(valor, salto) {
  const actual = Number.parseInt(valor, 10);
  const base = Number.isNaN(actual) ? 0 : actual;
  return String(Math.min(LIMITES.series[1], Math.max(LIMITES.series[0], base + salto)));
}

/** La carga de partida es una por ejercicio en toda la versión: escribirla en una fila la copia en las demás. */
export function fijarCargaPartida(semana, ejercicioId, valor) {
  for (const sesion of semana.sesiones) {
    for (const ejercicio of sesion.ejercicios) {
      if (ejercicio.ejercicio_id === ejercicioId) ejercicio.carga_partida = valor;
    }
  }
}

export function sustituirEjercicio(semana, ejercicioId, nuevo) {
  for (const sesion of semana.sesiones) {
    sesion.ejercicios = sesion.ejercicios.map((ejercicio) => (ejercicio.ejercicio_id === ejercicioId
      ? { ...filaNueva(nuevo), series: ejercicio.series }
      : ejercicio));
  }
}

export const idsDeEjercicios = (semana) => [...new Set(semana.sesiones.flatMap((sesion) => sesion.ejercicios.map((ejercicio) => ejercicio.ejercicio_id)))];

export function sesionesGeneradas(semana) {
  const semanas = Number.parseInt(semana.semanas, 10);
  return Number.isNaN(semanas) ? 0 : semanas * semana.sesiones.length;
}

/** Lo mismo que rechazaría la API, antes de enviar y con palabras del entrenador. */
export function problemasDeLaSemana(semana, catalogo, sugeridas = {}, plantilla = false) {
  const problemas = [];
  const semanas = Number(semana.semanas);
  if (!plantilla && (!Number.isInteger(semanas) || semanas < LIMITES.semanas[0] || semanas > LIMITES.semanas[1])) problemas.push("La duración va de 4 a 12 semanas.");
  if (semana.sesiones.length < LIMITES.sesiones[0]) problemas.push("Agregá al menos una sesión.");
  if (semana.sesiones.length > LIMITES.sesiones[1]) problemas.push("Una semana tiene hasta 6 sesiones.");
  semana.sesiones.forEach((sesion, indice) => {
    const nombre = sesion.nombre.trim() || `La sesión ${indice + 1}`;
    if (!sesion.nombre.trim()) problemas.push(`La sesión ${indice + 1} necesita un nombre.`);
    if (sesion.nombre.trim().length > 108) problemas.push(`${nombre}: el nombre admite hasta 108 caracteres.`);
    if (sesion.ejercicios.length < LIMITES.ejercicios[0]) problemas.push(`${nombre} no tiene ejercicios.`);
    if (sesion.ejercicios.length > LIMITES.ejercicios[1]) problemas.push(`${nombre} tiene más de 12 ejercicios.`);
    for (const ejercicio of sesion.ejercicios) {
      const datos = catalogo.get(ejercicio.ejercicio_id);
      const etiqueta = datos?.nombre ?? "Un ejercicio";
      const series = Number(ejercicio.series);
      if (!Number.isInteger(series) || series < LIMITES.series[0] || series > LIMITES.series[1]) problemas.push(`${etiqueta}: las series van de 1 a 10.`);
      if (campoAplica("repeticiones_minimas", datos)) {
        const minimas = Number(ejercicio.repeticiones_minimas);
        const maximas = Number(ejercicio.repeticiones_maximas);
        if (!ejercicio.repeticiones_minimas || !ejercicio.repeticiones_maximas || !(minimas >= 1) || !(maximas >= 1)) problemas.push(`${etiqueta}: indicá el rango de repeticiones.`);
        else if (minimas > maximas) problemas.push(`${etiqueta}: el mínimo de repeticiones no puede superar el máximo.`);
      }
      if (!plantilla && campoAplica("carga", datos) && !ejercicio.carga && !ejercicio.carga_partida && !sugeridas[ejercicio.ejercicio_id]) problemas.push(`${etiqueta}: no tiene historial; fijá una carga de partida.`);
      if (campoAplica("duracion", datos) && !ejercicio.duracion) problemas.push(`${etiqueta}: indicá la duración.`);
      if (campoAplica("distancia", datos) && !ejercicio.distancia) problemas.push(`${etiqueta}: indicá la distancia.`);
    }
  });
  return problemas;
}

function aEnviar(campo, texto) {
  if (texto === "" || texto === undefined) return null;
  return ENTEROS.has(campo) ? Number(texto) : texto;
}

export function cuerpoDePublicacion(semana, versionBase, catalogo, origen = null) {
  return {
    ...(origen?.startsWith("plantilla:") ? { plantilla_id: origen.slice(10) } : {}),
    version_base: versionBase,
    semanas: Number(semana.semanas),
    sesiones: semana.sesiones.map((sesion) => ({
      nombre: sesion.nombre.trim(),
      ejercicios: sesion.ejercicios.map((ejercicio) => {
        const datos = catalogo.get(ejercicio.ejercicio_id);
        const resultado = { ejercicio_id: ejercicio.ejercicio_id };
        for (const campo of CAMPOS) {
          if (campoAplica(campo, datos)) resultado[campo] = aEnviar(campo, ejercicio[campo]);
        }
        return resultado;
      }),
    })),
  };
}

export function cuerpoDePlantilla(semana, nombre, descripcion, catalogo) {
  const { sesiones } = cuerpoDePublicacion(semana, null, catalogo);
  for (const sesion of sesiones) {
    for (const ejercicio of sesion.ejercicios) {
      delete ejercicio.carga;
      delete ejercicio.carga_partida;
    }
  }
  return { nombre: nombre.trim(), descripcion: descripcion.trim(), sesiones };
}

// El formulario sobrevive a un corte de red o a una publicación fallida, solo en este navegador.
const claveDeFormulario = (socioId) => `gimnasio.editor-programa.${socioId}`;

export function conservarFormulario(almacen, socioId, datos) {
  try { almacen.setItem(claveDeFormulario(socioId), JSON.stringify(datos)); } catch { /* Sin almacenamiento se edita igual. */ }
}

export function leerFormulario(almacen, socioId) {
  try {
    const datos = JSON.parse(almacen.getItem(claveDeFormulario(socioId)));
    return Array.isArray(datos?.semana?.sesiones) ? datos : null;
  } catch {
    return null;
  }
}

export function olvidarFormulario(almacen, socioId) {
  try { almacen.removeItem(claveDeFormulario(socioId)); } catch { /* Nada que limpiar. */ }
}
