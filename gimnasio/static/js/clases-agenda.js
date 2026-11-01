// Lógica pura de la agenda: agrupa, dibuja el cupo en marcas y describe qué cambió entre dos lecturas.

const NOMBRES_DIA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const TITULOS_SEMANA = ["Esta semana", "La siguiente"];
// Más marcas ya no se leen de un vistazo: arriba de estos topes se usa una barra o un resto numérico.
export const TOPE_ASIENTOS = 30;
export const TOPE_ESPERA = 8;

export const fechaLegible = (valor) => valor.split("-").reverse().join("/");
export const claveOcurrencia = (fila) => `${fila.clase_id}|${fila.fecha}`;

function sumarDias(texto, dias) {
  const [anio, mes, dia] = texto.split("-").map(Number);
  return new Date(Date.UTC(anio, mes - 1, dia + dias)).toISOString().slice(0, 10);
}

/** Dos semanas de siete días desde `desde`, con cada ocurrencia en su día y por hora de inicio. */
export function semanasDeAgenda({ desde, ocurrencias }) {
  return TITULOS_SEMANA.map((titulo, semana) => {
    const dias = NOMBRES_DIA.map((nombre, indice) => {
      const fecha = sumarDias(desde, semana * 7 + indice);
      return {
        fecha, nombre,
        ocurrencias: ocurrencias.filter((fila) => fila.fecha === fecha)
          .sort((a, b) => String(a.hora_inicio).localeCompare(String(b.hora_inicio))),
      };
    });
    return { titulo, desde: dias[0].fecha, hasta: dias[6].fecha, dias };
  });
}

export function textoReserva(reserva) {
  return reserva.estado === "con_lugar" ? "Con lugar" : `En espera · Posición ${reserva.posicion}`;
}

const ocupados = (fila) => (fila.cancelada ? 0 : fila.cupo - fila.libres);

/** El asiento propio va siempre primero: así no salta cuando otro socio llega o se va. */
export function marcasDeCupo(fila) {
  const lleno = ocupados(fila);
  const propio = !fila.cancelada && fila.reserva?.estado === "con_lugar";
  const asientos = fila.cupo > TOPE_ASIENTOS ? null : Array.from({ length: fila.cupo }, (_, indice) => {
    if (propio && indice === 0) return "propio";
    return indice < lleno ? "ocupado" : "libre";
  });
  const visibles = Math.min(fila.espera, TOPE_ESPERA);
  const posicion = !fila.cancelada && fila.reserva?.estado === "en_espera"
    ? Math.min(fila.reserva.posicion, visibles) : 0;
  return {
    asientos,
    proporcion: fila.cupo > 0 ? lleno / fila.cupo : 0,
    espera: Array.from({ length: visibles }, (_, indice) => (indice + 1 === posicion ? "propio" : "espera")),
    restoEspera: fila.espera - visibles,
  };
}

function cambioPropio(antes, despues) {
  const anterior = antes.reserva;
  const actual = despues.reserva;
  if (despues.cancelada) return null;
  if (!anterior && actual) return actual.estado === "con_lugar" ? "reservo" : "quedo_en_espera";
  if (anterior && !actual) return "cancelo";
  if (!anterior) return null;
  if (anterior.estado === "en_espera" && actual.estado === "con_lugar") return "paso_a_tener_lugar";
  if (anterior.estado === "con_lugar" && actual.estado === "en_espera") return "volvio_a_espera";
  if (actual.estado === "en_espera" && actual.posicion < anterior.posicion) return "avanzo_en_espera";
  return null;
}

// La API no dice quién subió: solo se dibuja una subida cuando los números la prueban.
function subidasDeEspera(antes, despues, propio) {
  const bajaEspera = antes.espera - despues.espera;
  if (bajaEspera <= 0 || despues.cancelada) return 0;
  const sumados = ocupados(despues) - ocupados(antes);
  if (sumados > 0) return Math.min(sumados, bajaEspera);
  const liberoElPropio = propio === "cancelo" && antes.reserva.estado === "con_lugar";
  return propio === "paso_a_tener_lugar" || liberoElPropio ? 1 : 0;
}

function vuelosDeEspera(antes, despues, propio, subidas) {
  if (!subidas || despues.cupo > TOPE_ASIENTOS) return [];
  if (propio === "paso_a_tener_lugar") {
    return [{ desdeEspera: Math.min(antes.reserva.posicion, TOPE_ESPERA) - 1, asiento: 0 }];
  }
  const primero = ocupados(despues) - subidas;
  return Array.from({ length: subidas }, (_, indice) => ({
    desdeEspera: Math.min(indice, TOPE_ESPERA - 1), asiento: primero + indice,
  })).filter(({ asiento }) => asiento >= 0);
}

/** Describe qué cambió en una ocurrencia, o null si se ve igual. */
export function cambioDeOcurrencia(antes, despues) {
  const propio = cambioPropio(antes, despues);
  const cancelada = despues.cancelada && !antes.cancelada;
  const antesLleno = ocupados(antes);
  const lleno = ocupados(despues);
  const subidas = subidasDeEspera(antes, despues, propio);
  const entran = [];
  const salen = [];
  for (let indice = antesLleno; indice < lleno; indice++) entran.push(indice);
  for (let indice = lleno; indice < antesLleno; indice++) salen.push(indice);
  if (["reservo", "paso_a_tener_lugar"].includes(propio) && !entran.includes(0)) entran.unshift(0);
  const cifras = antes.libres !== despues.libres || antes.espera !== despues.espera || antes.cupo !== despues.cupo;
  if (!propio && !cancelada && !cifras) return null;
  return {
    clave: claveOcurrencia(despues), propio, cancelada, subidas, entran, salen, cifras,
    vuelos: vuelosDeEspera(antes, despues, propio, subidas),
  };
}

/** Compara dos lecturas de la agenda; las ocurrencias nuevas no se animan. */
export function cambiosDeAgenda(anteriores, actuales) {
  if (!anteriores) return [];
  const previas = new Map(anteriores.map((fila) => [claveOcurrencia(fila), fila]));
  return actuales.flatMap((fila) => {
    const previa = previas.get(claveOcurrencia(fila));
    const cambio = previa ? cambioDeOcurrencia(previa, fila) : null;
    return cambio ? [cambio] : [];
  });
}

const TEXTOS_ANUNCIO = {
  propio: {
    reservo: () => "Reserva confirmada, con lugar",
    quedo_en_espera: (fila) => `En lista de espera, posición ${fila.reserva.posicion}`,
    cancelo: () => "Reserva cancelada",
    paso_a_tener_lugar: () => "Ya tenés lugar",
    volvio_a_espera: (fila) => `Volviste a la lista de espera, posición ${fila.reserva.posicion}`,
    avanzo_en_espera: (fila) => `Avanzaste en la lista de espera, posición ${fila.reserva.posicion}`,
  },
  socio: {
    reservo: () => "Reserva confirmada, con lugar",
    quedo_en_espera: (fila) => `El socio quedó en lista de espera, posición ${fila.reserva.posicion}`,
    cancelo: () => "Reserva cancelada",
    paso_a_tener_lugar: () => "El socio pasó a tener lugar",
    volvio_a_espera: (fila) => `El socio volvió a la lista de espera, posición ${fila.reserva.posicion}`,
    avanzo_en_espera: (fila) => `El socio avanzó en la lista de espera, posición ${fila.reserva.posicion}`,
  },
};

/** Frase para el lector de pantalla: solo lo que le importa a quien mira, no cada cifra que se mueve. */
export function anuncioDeCambio(fila, cambio, voz = "propio") {
  const detalle = `${fila.clase}, ${fechaLegible(fila.fecha)} ${fila.hora_inicio}`;
  if (cambio.cancelada) return `Se canceló la ocurrencia: ${detalle}.`;
  if (!cambio.propio) return "";
  return `${TEXTOS_ANUNCIO[voz][cambio.propio](fila)}: ${detalle}.`;
}
