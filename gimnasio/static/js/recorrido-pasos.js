// Recorrido guiado (ADR 0032): los pasos y sus textos, sin DOM. Cada paso dice en qué pantalla y con qué
// sesión ocurre, a qué parte se ancla la tarjeta y qué frase muestra según el estado que encontró.

export const CLAVE_RECORRIDO = "gimnasio-recorrido";
// Unos dos minutos en total: seis esperas de lectura, tres narraciones y lo que tarda cada pantalla en cargar.
export const DURACION_PASO_MS = 12_000;
// Lo que se lee antes de una acción, para que se vea qué va a pasar antes de que pase.
export const DURACION_NARRACION_MS = 4_500;

// `sesion`: "cualquiera" no cambia de sesión; un rol entra como ese rol de la demo (el socio es Lucía).
// `ancla`: selectores en orden de preferencia; vale el primero visible. Sin ancla, la pantalla queda como está.
export const PASOS = [
  { id: "inicio", pagina: "/", sesion: "cualquiera", ancla: [] },
  { id: "entrada", pagina: "/recepcion.html", sesion: "recepcion", ancla: ["[data-tarjeta-contextual]", ".sede-cifras"] },
  { id: "escena", pagina: "/recepcion.html", sesion: "recepcion", ancla: ["[data-escena-ocupacion]", ".por-zona"] },
  { id: "chequeo", pagina: "/entrenamiento.html", sesion: "socio", ancla: ["[data-chequeo]", "[data-ejercicio]:has([data-ajuste]:not(:empty))", "[data-ejercicio]", "[data-contenido]"] },
  { id: "series", pagina: "/entrenamiento.html", sesion: "socio", ancla: ["[data-registro]", "[data-contenido]"] },
  { id: "freno", pagina: "/bandeja.html", sesion: "entrenador", ancla: ["[data-revision]", "[data-historial]", "[data-socio]", "[data-grupos]"] },
  { id: "resumen", pagina: "/resumen-sesion.html", sesion: "socio", ancla: ["[data-resumen]", "main"] },
];

export function iniciarRecorrido() {
  return { indice: 0, pausado: false, datos: {} };
}

// Lo guardado en el navegador puede venir de otra versión o estar roto: si no se entiende, no hay recorrido.
export function leerRecorrido(texto) {
  try {
    const estado = JSON.parse(texto);
    if (!Number.isInteger(estado?.indice) || estado.indice < 0 || estado.indice >= PASOS.length) return null;
    const datos = estado.datos && typeof estado.datos === "object" ? estado.datos : {};
    return { indice: estado.indice, pausado: estado.pausado === true, datos };
  } catch {
    return null;
  }
}

export const pasoActual = (estado) => PASOS[estado.indice];
export const esUltimo = (estado) => estado.indice === PASOS.length - 1;
export const progreso = (estado) => `Paso ${estado.indice + 1} de ${PASOS.length}`;

export function siguiente(estado) {
  return esUltimo(estado) ? null : { ...estado, indice: estado.indice + 1 };
}

// La sesión que hay que abrir para llegar al paso nuevo, o null si sirve la que ya está.
export function cambioDeSesion(anterior, nuevo) {
  if (nuevo.sesion === "cualquiera" || nuevo.sesion === anterior?.sesion) return null;
  return nuevo.sesion;
}

// La bandeja abre la hoja de Lucía y el resumen, la sesión que ella registró, si el recorrido ya los conoce.
export function destino(paso, datos = {}) {
  if (paso.id === "freno" && datos.lucia) return `${paso.pagina}?socio=${encodeURIComponent(datos.lucia)}`;
  if (paso.id === "resumen" && datos.sesion) return `${paso.pagina}?sesion=${encodeURIComponent(datos.sesion)}`;
  return paso.pagina;
}

const lugares = (ocupacion, aforo) => `${ocupacion} de ${aforo}`;
// Los mensajes de la API ya traen su punto final.
const conMotivo = (motivo) => (motivo ? `: ${motivo.replace(/\.$/, "")}.` : ".");

// Lo que se lee mientras la pantalla está por hacer la acción del paso.
export function textoDeNarracion(id, hechos = {}) {
  switch (id) {
    case "entrada":
      return hechos.aforo
        ? `Esto ve recepción: la ocupación de la sede al minuto, ${lugares(hechos.ocupacion, hechos.aforo)} lugares. Llega Lucía.`
        : "Esto ve recepción: la ocupación de la sede al minuto, contra su aforo máximo. Llega Lucía.";
    case "chequeo":
      return "Ahora sos Lucía. Antes de entrenar cuenta cómo llegó: durmió mal, sueño 1 de 5 y energía 2 de 5.";
    case "freno":
      return "Ahora sos su entrenador. Un freno de seguridad recortó la sesión de Lucía y le avisa por qué.";
    default:
      return "";
  }
}

// `hechos` es lo que el paso encontró o hizo en la pantalla real; ningún estado previo es un error (ADR 0032).
export function textoDelPaso(id, hechos = {}) {
  switch (id) {
    case "inicio":
      return "En unos dos minutos vas a ver la app real con datos ficticios: Lucía llega a la sede, cuenta que durmió mal, entrena y ve su resumen. Podés salir en cualquier paso.";
    case "entrada":
      if (hechos.resultado === "registrada") {
        return `Recepción registra su entrada: la ocupación pasa a ${lugares(hechos.ocupacion, hechos.aforo)}. La tarjeta contextual le muestra de un vistazo su membresía, sus pagos y sus visitas.`;
      }
      if (hechos.resultado === "ya-adentro") {
        return "Lucía ya está adentro: otra visita a la demo registró su entrada, que no se duplica. La tarjeta contextual muestra de un vistazo su membresía, sus pagos y sus visitas.";
      }
      return `Hoy no se pudo registrar la entrada de Lucía${conMotivo(hechos.motivo)} El recorrido sigue igual.`;
    case "escena":
      return hechos.conEscena
        ? "La escena de ocupación ubica cada visita en su zona de la sede: cada figura es una persona. Al costado, cuántas hay en cada zona."
        : "Por zona muestra dónde está cada visita. En el modo sin efectos es la misma información, sin la escena 3D.";
    case "chequeo":
      return hechos.chequeo === "guardado"
        ? "Como durmió mal, la propuesta le baja una serie y anula las subas de hoy. Cada ajuste explica por qué."
        : "La app le propone a Lucía la sesión de hoy y explica cada carga.";
    case "series":
      return hechos.resultado === "registrada"
        ? `Lucía empieza la sesión y registra ${hechos.series === 1 ? "una serie" : `${hechos.series} series`}, la primera de ${hechos.ejercicio}: cada una queda guardada al momento y arranca su descanso.`
        : `Lucía empieza la sesión, pero esta serie no se pudo guardar${conMotivo(hechos.motivo)} La sesión sigue abierta.`;
    case "freno":
      return hechos.resultado === "revisado"
        ? "El entrenador marca el aviso como revisado. Queda constancia de que lo vio; lo que hizo el freno no se deshace."
        : "Lucía no tiene avisos sin revisar: otra visita a la demo ya los revisó. Cada revisión queda en su historial.";
    case "resumen":
      if (!hechos.zonas) return "Este es el resumen de la sesión de Lucía. Terminá el recorrido para entrar con cualquier rol y explorar por tu cuenta.";
      return hechos.records
        ? `Lucía termina: su cuerpo se ilumina en lo que trabajó y ${hechos.records === 1 ? "bate un récord personal" : `bate ${hechos.records} récords personales`}. Terminá el recorrido para explorar con cualquier rol.`
        : "Lucía termina: su cuerpo se ilumina en lo que trabajó. Hoy no batió récords; cuando pasa, quedan acá. Terminá el recorrido para explorar con cualquier rol.";
    default:
      return "";
  }
}
