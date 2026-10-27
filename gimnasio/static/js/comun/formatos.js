// Formatos de Paraguay. Los vectores compartidos están en pruebas/vectores/formatos.json.

function agruparMiles(digitos) {
  return digitos.replace(/\B(?=(?:[0-9]{3})+$)/g, ".");
}

export function formatearGuaranies(importe) {
  if (typeof importe !== "bigint" && !Number.isInteger(importe)) throw new Error("El importe debe ser un entero");
  const entero = BigInt(importe);
  return `${entero < 0n ? "-" : ""}₲ ${agruparMiles(String(entero < 0n ? -entero : entero))}`;
}

/** Devuelve number en el rango seguro y bigint para conservar importes mayores sin redondear. */
export function parsearGuaranies(texto) {
  if (typeof texto !== "string") throw new Error("El importe debe ser texto");
  const coincidencia = /^(-?)(?:(?:₲|Gs\.) *)?([0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)$/.exec(texto.trim());
  if (!coincidencia) throw new Error("El importe debe estar en guaraníes sin decimales");
  const importe = BigInt(coincidencia[1] + coincidencia[2].replaceAll(".", ""));
  const limite = BigInt(Number.MAX_SAFE_INTEGER);
  return importe >= -limite && importe <= limite ? Number(importe) : importe;
}

export function normalizarCedula(texto) {
  if (typeof texto !== "string" || /[^0-9. ]/.test(texto)) {
    throw new Error("La cédula solo admite dígitos, puntos y espacios");
  }
  const digitos = texto.replace(/[. ]/g, "");
  if (digitos.length < 5 || digitos.length > 8) throw new Error("La cédula debe tener de 5 a 8 dígitos");
  return digitos;
}

export function formatearCedula(texto) {
  return agruparMiles(normalizarCedula(texto));
}

export function normalizarTelefono(texto) {
  if (typeof texto !== "string" || !/^ *\+?[0-9 ()-]+$/.test(texto) || /[\r\n\u2028\u2029]/.test(texto)) {
    throw new Error("El teléfono contiene caracteres inválidos");
  }
  const numero = texto.replace(/[ ()-]/g, "");
  let nacional;
  if (numero.startsWith("+")) {
    if (!numero.startsWith("+595")) throw new Error("El teléfono debe ser de Paraguay (+595)");
    nacional = numero.slice(4);
  } else if (numero.startsWith("595") && [11, 12].includes(numero.length)) {
    nacional = numero.slice(3);
  } else {
    nacional = numero.replace(/^0/, "");
  }
  if (!/^(?:9[0-9]{8}|[2-8][0-9]{7,8})$/.test(nacional)) {
    throw new Error("El teléfono debe ser un celular o fijo de Paraguay");
  }
  return "+595" + nacional;
}

export function formatearTelefono(texto) {
  const nacional = normalizarTelefono(texto).slice(4);
  if (nacional.startsWith("9")) return `+595 ${nacional.slice(0, 3)} ${nacional.slice(3, 6)} ${nacional.slice(6)}`;
  return `+595 ${nacional.slice(0, 2)} ${nacional.slice(2)}`;
}

function validarFecha(texto) {
  if (typeof texto !== "string" || texto.length !== 10 || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(texto)) {
    throw new Error("Se requiere una fecha ISO (aaaa-mm-dd)");
  }
  const [anio, mes, dia] = texto.split("-").map(Number);
  const fecha = new Date(0);
  fecha.setUTCFullYear(anio, mes - 1, dia);
  if (anio < 1 || fecha.getUTCFullYear() !== anio || fecha.getUTCMonth() !== mes - 1 || fecha.getUTCDate() !== dia) {
    throw new Error("Fecha inválida");
  }
}

/** Recibe una fecha de calendario ISO (aaaa-mm-dd), sin conversión de zona. */
export function formatearFecha(texto) {
  validarFecha(texto);
  return `${texto.slice(8, 10)}/${texto.slice(5, 7)}/${texto.slice(0, 4)}`;
}

/** Carga de la API en kg: el valor decimal permanece intacto, solo cambia su presentación. */
export function formatearCarga(valor) {
  if ((typeof valor !== "number" && typeof valor !== "string") || String(valor).trim() === ""
      || !Number.isFinite(Number(valor)) || Number(valor) < 0) throw new Error("Se requiere una carga válida en kg");
  return `${new Intl.NumberFormat("es-PY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(valor))} kg`;
}

/** Recibe un ISO 8601 con zona; la salida usa la zona de la sede por defecto. */
export function formatearFechaHora(texto, zona = "America/Asuncion") {
  if (typeof texto !== "string") throw new Error("Se requiere una fecha y hora con zona horaria");
  const coincidencia = /^([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.[0-9]+)?)?(Z|[+-][0-9]{2}:[0-9]{2})$/.exec(texto);
  if (!coincidencia || coincidencia[0] !== texto) throw new Error("Se requiere una fecha y hora ISO con zona horaria");
  validarFecha(coincidencia[1]);
  if (Number(coincidencia[2]) > 23 || Number(coincidencia[3]) > 59 || Number(coincidencia[4] ?? 0) > 59) {
    throw new Error("Hora inválida");
  }
  const fecha = new Date(texto);
  if (Number.isNaN(fecha.getTime())) throw new Error("Fecha y hora inválidas");
  if (typeof zona !== "string") throw new Error("La zona horaria debe ser texto");
  const formato = new Intl.DateTimeFormat("en-GB", {
    timeZone: zona, calendar: "gregory", numberingSystem: "latn", hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
  const partes = Object.fromEntries(formato.formatToParts(fecha).map(({ type: tipo, value: valor }) => [tipo, valor]));
  return `${partes.day}/${partes.month}/${partes.year.padStart(4, "0")} ${partes.hour}:${partes.minute}`;
}
