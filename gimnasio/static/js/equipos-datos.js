// Reglas de presentación de equipos y alternativas, sin DOM.

const MOTIVOS_DE_RECHAZO = [
  [(ejercicio, candidato) => candidato.id === ejercicio.id, "es el mismo ejercicio"],
  [(ejercicio, candidato) => candidato.patron_movimiento !== ejercicio.patron_movimiento, "otro patrón de movimiento"],
  [(ejercicio, candidato) => candidato.equipo === ejercicio.equipo, "mismo equipo"],
];

// El catálogo guarda claves sin tilde; en pantalla va la palabra bien escrita.
const NOMBRES_DE_EQUIPO = { cajon: "cajón" };
export const nombreDeEquipo = (equipo) => NOMBRES_DE_EQUIPO[equipo] ?? equipo;

export function motivoDeRechazo(ejercicio, candidato) {
  return MOTIVOS_DE_RECHAZO.find(([rechaza]) => rechaza(ejercicio, candidato))?.[1] ?? null;
}

/** Candidatos para agregar: primero los válidos; los demás quedan a la vista con el motivo, sin poder elegirse. */
export function candidatosDeAlternativa(ejercicio, catalogo) {
  return catalogo
    .filter((candidato) => candidato.id !== ejercicio.id && !ejercicio.alternativas.includes(candidato.id))
    .map((candidato) => ({ candidato, motivo: motivoDeRechazo(ejercicio, candidato) }))
    .sort((a, b) => Number(Boolean(a.motivo)) - Number(Boolean(b.motivo)) || a.candidato.nombre.localeCompare(b.candidato.nombre, "es"));
}

/** Si el equipo del ejercicio se apaga, ¿tiene adónde ir? */
export function sinAlternativaDisponible(ejercicio, porId) {
  return !ejercicio.alternativas.some((id) => porId.get(id)?.estado_equipo === "disponible");
}

export const ejerciciosDelEquipo = (equipo, catalogo) => catalogo.filter((ejercicio) => ejercicio.equipo === equipo.nombre);

/** La API cita el identificador del ejercicio rechazado: en pantalla va su nombre. */
export function mensajeLegible(mensaje, porId) {
  return mensaje.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, (id) => porId.get(id)?.nombre ?? "El ejercicio");
}

export function moverEnLista(lista, indice, salto) {
  const destino = indice + salto;
  if (destino < 0 || destino >= lista.length) return lista;
  const copia = [...lista];
  [copia[indice], copia[destino]] = [copia[destino], copia[indice]];
  return copia;
}
