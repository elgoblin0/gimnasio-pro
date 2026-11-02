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
