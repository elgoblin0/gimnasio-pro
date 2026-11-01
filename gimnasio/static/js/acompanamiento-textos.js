// Textos de la incorporación y del riesgo de abandono, sin DOM: la API entrega códigos y datos.

export const textoDia = (dia) => `Día ${dia} de 90`;

const HITOS = {
  programa_asignado: "Programa asignado",
  primera_visita: "Primera visita",
  primera_sesion: "Primera sesión realizada",
};

export const textosDeHitos = (hitos) =>
  Object.entries(HITOS).map(([clave, texto]) => ({ texto, cumplido: Boolean(hitos[clave]) }));

const fechaCorta = (iso) => iso.split("-").reverse().join("/");

const RAZONES = {
  ausencia: ({ dias }) => `${dias} días sin venir`,
  tendencia: ({ recientes, anteriores }) => `Bajó de ${anteriores} a ${recientes} visitas en cuatro semanas`,
  membresia_vencida: ({ hasta }) => `Membresía vencida el ${fechaCorta(hasta)}`,
};

export const textosDeRiesgo = (razones) =>
  razones.map(({ regla, datos }) => RAZONES[regla]?.(datos) ?? regla);
