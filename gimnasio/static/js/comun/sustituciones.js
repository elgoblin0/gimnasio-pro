// El socio ve el motivo de una sustitución sin el detalle de salud (freno 2).
const MOTIVOS_SUSTITUCION = {
  maquina_ocupada: "máquina ocupada",
  dolor_reportado: "dolor reportado",
  restriccion_salud: "restricción registrada por tu entrenador",
};

export function textoMotivoSustitucion(motivo) {
  return MOTIVOS_SUSTITUCION[motivo] ?? motivo;
}
