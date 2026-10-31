const activos = new Set();

// Una consulta posterior al cierre de sesión volvería con 401: se frena antes de pedirlo.
export function pausarSondeos() {
  const pausados = [...activos];
  pausados.forEach((sondeo) => sondeo.detener());
  return () => pausados.forEach((sondeo) => sondeo.reanudar());
}

// Peticiones cortas sin solaparse; el navegador oculto no consume consultas.
export function crearSondeo({ url, cadaMs = 5000, alCambiar, alFallar = () => {}, puedeConsultar = () => true }) {
  let etiqueta;
  let espera = cadaMs;
  let temporizador;
  let enCurso = false;
  let detenido = false;
  let generacion = 0;
  let cancelacion;
  const documento = globalThis.document;

  function programar() {
    clearTimeout(temporizador);
    if (!detenido && !documento?.hidden) temporizador = setTimeout(actualizar, espera);
  }

  async function actualizar() {
    if (detenido || documento?.hidden || enCurso) return;
    if (!puedeConsultar()) { programar(); return; }
    clearTimeout(temporizador);
    enCurso = true;
    const actual = generacion;
    const { signal } = cancelacion = new AbortController();
    try {
      const respuesta = await fetch(url, {
        credentials: "same-origin", cache: "no-store", signal,
        headers: etiqueta ? { "If-None-Match": etiqueta } : {},
      });
      if (respuesta.status !== 304) {
        if (respuesta.status !== 200) throw new Error("No se pudo consultar.");
        const datos = await respuesta.json();
        if (!detenido && actual === generacion && puedeConsultar()) {
          alCambiar(datos);
          etiqueta = respuesta.headers.get("ETag");
        }
      }
      espera = cadaMs;
    } catch {
      if (!signal.aborted) {
        espera = Math.min(30000, espera * 2);
        alFallar();
      }
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
  const sondeo = {
    actualizar,
    invalidar() { generacion++; etiqueta = undefined; },
    detener() {
      detenido = true;
      activos.delete(sondeo);
      clearTimeout(temporizador);
      cancelacion?.abort();
      documento?.removeEventListener("visibilitychange", visibilidad);
    },
    reanudar() {
      if (!detenido) return;
      detenido = false;
      activos.add(sondeo);
      documento?.addEventListener("visibilitychange", visibilidad);
      if (enCurso) programar();
      else actualizar();
    },
  };
  activos.add(sondeo);
  return sondeo;
}
