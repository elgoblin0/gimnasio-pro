// Textos de la bandeja y de los avisos, sin DOM: la API entrega códigos y fechas.

export const GRUPOS_BANDEJA = Object.freeze({
  aviso_seguridad: "Avisos por dolor o restricción",
  sin_programa: "Sin programa",
  secuencia_terminada: "Secuencia terminada",
  ejercicio_sin_alternativa: "Ejercicio sin alternativa disponible",
  sin_consentimiento_salud: "Sin consentimiento de salud",
  aviso_progresion: "Avisos por chequeo o tope",
});

const MOTIVOS = {
  aviso_seguridad: ["Aviso por dolor o restricción", "avisos por dolor o restricción"],
  sin_programa: ["Sin programa"],
  secuencia_terminada: ["Secuencia terminada"],
  ejercicio_sin_alternativa: ["Ejercicio sin alternativa", "ejercicios sin alternativa"],
  sin_consentimiento_salud: ["Sin consentimiento de salud"],
  aviso_progresion: ["Aviso por chequeo o tope", "avisos por chequeo o tope"],
};

const FRENOS = {
  dolor_reportado: "Dolor reportado",
  restriccion_salud: "Restricción de salud",
  chequeo_desfavorable: "Chequeo del día desfavorable",
  tope_semanal: "Tope semanal",
};

export const textoFreno = (freno) => FRENOS[freno] ?? "Aviso al entrenador";

/** Un socio aparece una sola vez: sus motivos se resumen en una lista sin repetidos, en orden de prioridad. */
export function textosDeMotivos(motivos) {
  const cuenta = new Map();
  for (const { tipo } of motivos) cuenta.set(tipo, (cuenta.get(tipo) ?? 0) + 1);
  return Object.keys(GRUPOS_BANDEJA)
    .filter((tipo) => cuenta.has(tipo))
    .map((tipo) => {
      const [uno, varios] = MOTIVOS[tipo];
      return cuenta.get(tipo) === 1 ? uno : `${cuenta.get(tipo)} ${varios}`;
    });
}

export function contarSocios(grupos) {
  return grupos.reduce((total, grupo) => total + grupo.socios.length, 0);
}

/** Antigüedad legible del motivo más viejo del grupo: dentro de cada grupo van primero los más antiguos. */
export function antiguedad(fechaIso, ahoraMs) {
  const minutos = Math.floor((ahoraMs - new Date(fechaIso).getTime()) / 60000);
  if (!(minutos >= 1)) return "recién";
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  return dias === 1 ? "hace 1 día" : `hace ${dias} días`;
}

/** Sin consentimiento de salud la API quita el texto del freno: queda el nombre del freno y el ejercicio. */
export function explicacionDeAviso(aviso, nombreDeEjercicio = () => null) {
  const textos = [];
  const ejercicios = [];
  for (const { datos } of aviso.explicacion ?? []) {
    if (datos?.explicacion) textos.push(datos.explicacion);
    const nombre = datos?.ejercicio_id ? nombreDeEjercicio(datos.ejercicio_id) : null;
    if (nombre && !ejercicios.includes(nombre)) ejercicios.push(nombre);
  }
  return { textos: [...new Set(textos)], ejercicios };
}

export const avisosSinRevisar = (avisos) => avisos.filter((aviso) => !aviso.revisado);

/** Socios que entraron a la bandeja o recibieron un aviso desde la lectura anterior. */
export function sociosConNovedad(anteriores, grupos) {
  const novedades = [];
  for (const grupo of grupos) {
    for (const socio of grupo.socios) {
      const claves = socio.motivos.map(claveDeMotivo);
      const previas = anteriores.get(socio.id);
      if (!previas || claves.some((clave) => !previas.has(clave))) novedades.push(socio);
    }
  }
  return novedades;
}

export function motivosPorSocio(grupos) {
  const resultado = new Map();
  for (const grupo of grupos) {
    for (const socio of grupo.socios) resultado.set(socio.id, new Set(socio.motivos.map(claveDeMotivo)));
  }
  return resultado;
}

const claveDeMotivo = (motivo) => `${motivo.tipo}:${motivo.aviso_id ?? motivo.ejercicio_id ?? ""}`;
