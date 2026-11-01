// Textos del resumen semanal, sin DOM: la API entrega cantidades y razones.

const fechaCorta = (iso) => iso.split("-").reverse().slice(0, 2).join("/");
const numero = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });
const plural = (cantidad, uno, varios) => `${cantidad} ${cantidad === 1 ? uno : varios}`;

export const textoSemana = ({ lunes, domingo }) => `Semana del ${fechaCorta(lunes)} al ${fechaCorta(domingo)}`;

export function textosCumplido({ sesiones_realizadas, sesiones_planificadas, series, volumen, visitas }) {
  const partes = [
    sesiones_planificadas
      ? `${sesiones_realizadas} de ${plural(sesiones_planificadas, "sesión planificada", "sesiones planificadas")}`
      : plural(sesiones_realizadas, "sesión realizada", "sesiones realizadas"),
    plural(series, "serie", "series"),
  ];
  if (volumen.repeticiones) partes.push(plural(volumen.repeticiones, "repetición", "repeticiones"));
  if (volumen.duracion) partes.push(`${numero.format(volumen.duracion / 60)} min`);
  if (Number(volumen.distancia)) partes.push(`${numero.format(Number(volumen.distancia))} m`);
  partes.push(plural(visitas, "visita", "visitas"));
  return partes;
}

const FRENOS = {
  dolor_reportado: "Actuó el freno por dolor reportado",
  restriccion_salud: "Actuó el freno por restricción de salud",
  chequeo_desfavorable: "Actuó el freno por chequeo del día desfavorable",
  tope_semanal: "Actuó el tope semanal de subas",
};

// Sin consentimiento de salud, el entrenador recibe la regla sin su explicación (ADR 0024).
export const textosCambios = ({ ajustes, frenos }) => [
  ...ajustes.map((razon) => razon.datos.explicacion ?? razon.regla),
  ...frenos.map((razon) => razon.datos.explicacion ?? FRENOS[razon.regla] ?? razon.regla),
];

export function textosPendientes({ series, sesiones_sin_realizar }) {
  const textos = series.map(({ nombre, series: numeros }) =>
    `${nombre}: ${plural(numeros.length, "serie sin hacer", "series sin hacer")}`);
  if (sesiones_sin_realizar) {
    textos.push(plural(sesiones_sin_realizar, "sesión planificada sin realizar", "sesiones planificadas sin realizar"));
  }
  return textos;
}
