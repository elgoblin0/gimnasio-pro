// Peticiones cortas sin solaparse; el navegador oculto no consume consultas.
export function crearSondeo({ url, cadaMs = 5000, alCambiar }) {
  let etiqueta;
  let espera = cadaMs;
  let temporizador;
  let enCurso = false;
  let detenido = false;
  let generacion = 0;
  const documento = globalThis.document;

  function programar() {
    clearTimeout(temporizador);
    if (!detenido && !documento?.hidden) temporizador = setTimeout(actualizar, espera);
  }

  async function actualizar() {
    if (detenido || documento?.hidden || enCurso) return;
    clearTimeout(temporizador);
    enCurso = true;
    const actual = generacion;
    try {
      const respuesta = await fetch(url, {
        credentials: "same-origin", cache: "no-store",
        headers: etiqueta ? { "If-None-Match": etiqueta } : {},
      });
      if (respuesta.status !== 304) {
        if (respuesta.status !== 200) throw new Error("No se pudo consultar.");
        const datos = await respuesta.json();
        if (!detenido && actual === generacion) {
          alCambiar(datos);
          etiqueta = respuesta.headers.get("ETag");
        }
      }
      espera = cadaMs;
    } catch {
      espera = Math.min(30000, espera * 2);
    } finally {
      enCurso = false;
      programar();
    }
  }

  function visibilidad() {
    clearTimeout(temporizador);
    if (!documento.hidden) actualizar();
  }
  documento?.addEventListener("visibilitychange", visibilidad);
  actualizar();
  return {
    actualizar,
    invalidar() { generacion++; etiqueta = undefined; },
    detener() {
      detenido = true;
      clearTimeout(temporizador);
      documento?.removeEventListener("visibilitychange", visibilidad);
    },
  };
}
