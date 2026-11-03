// Textos y decisiones de la pantalla de entrenamiento, sin DOM.

import { formatearCarga } from "./comun/formatos.js";

const numero = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });
const REGLAS_QUE_QUITAN = ["dolor_reportado", "restriccion_salud"];

export const seQuito = (ejercicio) => ejercicio.objetivos.series === 0;

const duracionLegible = (segundos) => (segundos >= 60 && segundos % 60 === 0 ? `${segundos / 60} min` : `${segundos} s`);

export function describirObjetivos(objetivos) {
  const partes = [`${objetivos.series} ${objetivos.series === 1 ? "serie" : "series"}`];
  if (objetivos.repeticiones_minimas != null) {
    partes.push(objetivos.repeticiones_minimas === objetivos.repeticiones_maximas
      ? `${objetivos.repeticiones_minimas} reps`
      : `${objetivos.repeticiones_minimas}–${objetivos.repeticiones_maximas} reps`);
  }
  if (objetivos.repeticiones != null) partes.push(`${objetivos.repeticiones} repeticiones`);
  if (objetivos.carga !== null) partes.push(formatearCarga(objetivos.carga));
  if (objetivos.duracion !== null) partes.push(duracionLegible(objetivos.duracion));
  if (objetivos.distancia !== null) partes.push(`${numero.format(Number(objetivos.distancia))} m`);
  return partes.join(" · ");
}

// Un ejercicio no disponible sigue pendiente, pero hoy tampoco se puede hacer.
export function sinTrabajoHoy(ejercicios) {
  return ejercicios.length > 0 && ejercicios.every((ejercicio) => seQuito(ejercicio) || ejercicio.no_disponible);
}

// De un ejercicio quitado importa por qué se quitó: lo que se le iba a prescribir ya no rige.
export function razonesVisibles(ejercicio) {
  const razones = ejercicio.explicacion ?? [];
  const delFreno = razones.filter((razon) => REGLAS_QUE_QUITAN.includes(razon.regla));
  return seQuito(ejercicio) && delFreno.length ? delFreno : razones;
}

export function mensajeDeOperacion(datos, { avisando = false } = {}) {
  if (datos.chequeo) return "Chequeo guardado.";
  if (datos.dolor_reportado) return "Dolor reportado guardado. Se avisó al entrenador.";
  if (datos.sesion_realizada) return avisando ? "Aviso enviado a tu entrenador." : "Sesión iniciada.";
  if (datos.sustitucion) return "Sustitución guardada.";
  return "Serie guardada.";
}

const sePuedeHacer = (ejercicio) => ejercicio.pendiente > 0 && !ejercicio.no_disponible && !seQuito(ejercicio);

// Un ejercicio a la vez: el que eligió el socio mientras le falte algo; si no, el primero con series pendientes.
export function ejercicioEnFoco(ejercicios, elegido) {
  const delSocio = ejercicios.find((ejercicio) => ejercicio.id === elegido);
  if (delSocio && sePuedeHacer(delSocio)) return delSocio.id;
  return ejercicios.find(sePuedeHacer)?.id ?? null;
}

export function avanceDeSesion(ejercicios) {
  const hechas = ejercicios.reduce((total, ejercicio) => total + ejercicio.realizado, 0);
  const total = hechas + ejercicios.filter((ejercicio) => !seQuito(ejercicio)).reduce((suma, ejercicio) => suma + ejercicio.pendiente, 0);
  return { hechas, total, texto: `${hechas} de ${total} ${total === 1 ? "serie" : "series"}` };
}

// El panel del día: con series pendientes todavía se puede seguir; sin ellas, ya está.
export function estadoDelDia(realizada) {
  const pendientes = realizada.ejercicios.some(sePuedeHacer);
  const cantidad = realizada.series.length;
  return {
    pendientes,
    titulo: pendientes ? "Tenés una sesión empezada" : "Listo por hoy",
    texto: `${realizada.sesion_planificada.nombre}: ${cantidad} ${cantidad === 1 ? "serie guardada" : "series guardadas"}.`,
  };
}

export function formatearDuracion(segundos) {
  if (segundos < 60) return "menos de 1 min";
  const minutos = Math.round(segundos / 60);
  return minutos < 60 ? `${minutos} min` : `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}

export function describirVolumen({ series, repeticiones, duracion, distancia }) {
  const partes = [`${series} ${series === 1 ? "serie" : "series"}`];
  if (repeticiones) partes.push(`${numero.format(repeticiones)} repeticiones`);
  if (duracion) partes.push(formatearDuracion(duracion));
  if (Number(distancia)) partes.push(`${numero.format(Number(distancia))} m`);
  return partes.join(" · ");
}

// Lo que sigue después de esta sesión: lo que quedó de ella, la próxima con trabajo o el fin del programa.
export function proximoPaso(propuesta, sesionPlanificadaId) {
  if (propuesta.sesion_planificada && propuesta.sesion_planificada.id === sesionPlanificadaId) return `Te quedan series de ${propuesta.sesion_planificada.nombre} para la próxima vez.`;
  if (propuesta.sesion_planificada) return `Tu próxima sesión es ${propuesta.sesion_planificada.nombre}.`;
  return propuesta.explicacion[0]?.regla === "sin_programa"
    ? "Tu entrenador te va a asignar un programa."
    : "Terminaste tu programa; tu entrenador prepara el siguiente.";
}
