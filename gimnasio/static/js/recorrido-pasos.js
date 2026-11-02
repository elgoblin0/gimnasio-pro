// Recorrido guiado (ADR 0032): los pasos y sus textos, sin DOM. Cada paso dice en qué pantalla y con qué
// sesión ocurre, a qué parte se ancla la tarjeta y qué frase muestra según el estado que encontró.

export const CLAVE_RECORRIDO = "gimnasio-recorrido";
// Unos dos minutos en total, sin contar lo que tarda cada pantalla en cargar.
export const DURACION_PASO_MS = 12_000;

// `sesion`: "cualquiera" no cambia de sesión; "ninguna" la cierra; un rol entra como ese rol de la demo
// (el socio es Lucía). `ancla`: selectores en orden de preferencia; vale el primero visible.
export const PASOS = [
  { id: "inicio", pagina: "/", sesion: "cualquiera", ancla: ["[data-recorrido-portada]", ".portada-presentacion"] },
  { id: "aforo", pagina: "/recepcion.html", sesion: "recepcion", ancla: [".sede-cifras"] },
  { id: "entrada", pagina: "/recepcion.html", sesion: "recepcion", ancla: [".sede-cifras"] },
  { id: "escena", pagina: "/recepcion.html", sesion: "recepcion", ancla: ["[data-escena-ocupacion]", ".por-zona"] },
  { id: "propuesta", pagina: "/entrenamiento.html", sesion: "socio", ancla: ["[data-ejercicio]", "[data-contenido]"] },
  { id: "series", pagina: "/entrenamiento.html", sesion: "socio", ancla: ["[data-registro]", "[data-contenido]"] },
  { id: "freno", pagina: "/bandeja.html", sesion: "entrenador", ancla: ["[data-revision]", "[data-historial]", "[data-socio]", "[data-grupos]"] },
  { id: "revision", pagina: "/bandeja.html", sesion: "entrenador", ancla: ["[data-avisos-revisados] > li", "[data-historial]", "[data-revision]", "[data-socio]", "[data-grupos]"] },
  { id: "administracion", pagina: "/administracion.html", sesion: "administracion", ancla: ["#sede", "main"] },
  { id: "explorar", pagina: "/", sesion: "ninguna", ancla: ["[data-demo]", ".portada-ingreso"] },
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

// La bandeja abre la hoja de Lucía si el recorrido ya conoce su id.
export function destino(paso, datos = {}) {
  if (paso.id === "freno" || paso.id === "revision") {
    return datos.lucia ? `${paso.pagina}?socio=${encodeURIComponent(datos.lucia)}` : paso.pagina;
  }
  return paso.pagina;
}

const lugares = (ocupacion, aforo) => `${ocupacion} de ${aforo}`;
// Los mensajes de la API ya traen su punto final.
const conMotivo = (motivo) => (motivo ? `: ${motivo.replace(/\.$/, "")}.` : ".");

// `hechos` es lo que el paso encontró o hizo en la pantalla real; ningún estado previo es un error (ADR 0032).
export function textoDelPaso(id, hechos = {}) {
  switch (id) {
    case "inicio":
      return "En unos dos minutos vas a ver la app real con datos ficticios: Lucía entra a la sede, entrena y su entrenador revisa un freno. Podés salir en cualquier paso.";
    case "aforo":
      return hechos.aforo
        ? `Esto ve recepción: la ocupación de la sede al minuto, ${lugares(hechos.ocupacion, hechos.aforo)} lugares.`
        : "Esto ve recepción: la ocupación de la sede al minuto, contra su aforo máximo.";
    case "entrada":
      if (hechos.resultado === "registrada") {
        return `Lucía llega y recepción registra su entrada: la ocupación pasa a ${lugares(hechos.ocupacion, hechos.aforo)}.`;
      }
      if (hechos.resultado === "ya-adentro") {
        return "Lucía ya está adentro: otra visita a la demo registró su entrada. La entrada no se duplica.";
      }
      return `Hoy no se pudo registrar la entrada de Lucía${conMotivo(hechos.motivo)} El recorrido sigue igual.`;
    case "escena":
      return hechos.conEscena
        ? "La escena de ocupación ubica cada visita en su zona de la sede. Tocá un punto para ver de quién es."
        : "Por zona muestra dónde está cada visita. En el modo sin efectos es la misma información, sin la escena 3D.";
    case "propuesta":
      return hechos.chequeo === "guardado"
        ? "Ahora sos Lucía. Contó que durmió mal: la propuesta le baja una serie, anula las subas de hoy y explica por qué."
        : "Ahora sos Lucía. La app le propone la sesión de hoy y explica cada carga.";
    case "series":
      return hechos.resultado === "registrada"
        ? `Lucía empieza la sesión y registra una serie de ${hechos.ejercicio}: queda guardada al momento y arranca su descanso.`
        : `Lucía empieza la sesión, pero esta serie no se pudo guardar${conMotivo(hechos.motivo)} La sesión sigue abierta.`;
    case "freno":
      return hechos.avisos > 0
        ? "Ahora sos su entrenador. Un freno de seguridad recortó la sesión de Lucía y le avisa por qué."
        : "Ahora sos su entrenador. Lucía no tiene avisos sin revisar: otra visita a la demo ya los revisó.";
    case "revision":
      return hechos.resultado === "revisado"
        ? "El entrenador marca el aviso como revisado. Queda constancia de que lo vio; lo que hizo el freno no se deshace."
        : "No quedaba nada por revisar: cada revisión queda en el historial de avisos de Lucía.";
    case "administracion":
      return "Ahora sos administración: la sede con su aforo y su horario. Cada cambio queda registrado con su motivo.";
    case "explorar":
      return "Eso es Gimnasio Pro. Entrá como cualquier rol y explorá por tu cuenta: lo que hizo el recorrido sigue ahí.";
    default:
      return "";
  }
}
