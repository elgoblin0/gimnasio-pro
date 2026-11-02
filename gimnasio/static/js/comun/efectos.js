// Modo sin efectos (glosario): sin escenas 3D ni animaciones decorativas, con la misma información y las mismas acciones.
// La elección del interruptor manda sobre la detección y se recuerda por navegador.

export const CLAVE_ELECCION = "gimnasio-sin-efectos";

// Sin GPU, cada sombra se calcula en la CPU y compite con el resto de la pantalla.
export function esDibujoPorSoftware(renderizador) {
  return /swiftshader|llvmpipe|softpipe|software|basic render/i.test(renderizador ?? "");
}

// Regla pura. `grafica` se consulta solo si nada anterior decide, porque crear un contexto WebGL cuesta.
export function decidirModoSinEfectos({ eleccion = null, movimientoReducido = false, nucleos, memoria, grafica }) {
  if (eleccion === "si") return { activo: true, motivo: "eleccion" };
  if (eleccion === "no") return { activo: false, motivo: "eleccion" };
  if (movimientoReducido) return { activo: true, motivo: "movimiento-reducido" };
  if (nucleos <= 2 || memoria <= 2) return { activo: true, motivo: "equipo-lento" };
  const { webgl2, renderizador } = grafica();
  if (!webgl2) return { activo: true, motivo: "sin-webgl" };
  if (esDibujoPorSoftware(renderizador)) return { activo: true, motivo: "software" };
  return { activo: false, motivo: null };
}

export const MOTIVOS = {
  "eleccion": "elegido en este navegador",
  "movimiento-reducido": "el equipo pide movimiento reducido",
  "equipo-lento": "el equipo tiene pocos recursos",
  "sin-webgl": "el navegador no dibuja 3D",
  "software": "el equipo dibuja sin tarjeta gráfica",
};

const graficas = new WeakMap();

// Una sola prueba de WebGL2 por documento; la comparten la regla, el cuerpo 3D y la escena de ocupación.
export function graficaDisponible(documento = globalThis.document) {
  if (!documento) return { webgl2: false, renderizador: "" };
  if (!graficas.has(documento)) {
    let resultado = { webgl2: false, renderizador: "" };
    try {
      const contexto = documento.createElement("canvas").getContext("webgl2");
      if (contexto) {
        const extension = contexto.getExtension("WEBGL_debug_renderer_info");
        const renderizador = extension ? contexto.getParameter(extension.UNMASKED_RENDERER_WEBGL) : "";
        contexto.getExtension("WEBGL_lose_context")?.loseContext();
        resultado = { webgl2: true, renderizador };
      }
    } catch { /* Sin WebGL2. */ }
    graficas.set(documento, resultado);
  }
  return graficas.get(documento);
}

function leerEleccion(ventana) {
  try {
    const valor = ventana?.localStorage?.getItem(CLAVE_ELECCION);
    return valor === "si" || valor === "no" ? valor : null;
  } catch { return null; }
}

export function modoSinEfectos(documento = globalThis.document) {
  const ventana = documento?.defaultView ?? globalThis;
  return decidirModoSinEfectos({
    eleccion: leerEleccion(ventana),
    movimientoReducido: !ventana.matchMedia || ventana.matchMedia("(prefers-reduced-motion: reduce)").matches,
    nucleos: ventana.navigator?.hardwareConcurrency,
    memoria: ventana.navigator?.deviceMemory,
    grafica: () => graficaDisponible(documento),
  });
}

// Las escenas leen el estado al cargar: cambiarlo recarga la página para que todas lo tomen igual.
export function montarInterruptorEfectos(documento = globalThis.document) {
  // Una página puede reservarle su lugar; si no, va al final de la cabecera.
  const lugar = documento.querySelector("[data-lugar-efectos]") ?? documento.querySelector("body > header") ?? documento.querySelector("main");
  if (!lugar) return;
  const estado = modoSinEfectos(documento);
  documento.documentElement.dataset.sinEfectos = estado.activo ? "si" : "no";
  const boton = documento.createElement("button");
  boton.type = "button";
  boton.className = "interruptor-efectos";
  boton.dataset.interruptorEfectos = "";
  boton.setAttribute("aria-pressed", String(estado.activo));
  boton.textContent = "Modo sin efectos";
  if (estado.motivo) boton.title = `${estado.activo ? "Activado" : "Desactivado"}: ${MOTIVOS[estado.motivo]}`;
  boton.addEventListener("click", () => {
    try {
      documento.defaultView.localStorage.setItem(CLAVE_ELECCION, estado.activo ? "no" : "si");
      documento.defaultView.location.reload();
    } catch {
      // Sin almacenamiento no hay qué recordar: solo se apagan las animaciones de esta página.
      estado.activo = !estado.activo;
      documento.documentElement.dataset.sinEfectos = estado.activo ? "si" : "no";
      boton.setAttribute("aria-pressed", String(estado.activo));
    }
  });
  lugar.append(boton);
}
