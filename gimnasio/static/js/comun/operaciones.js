import { nuevoId } from "./ids.js";

// Solo en memoria. Volver a tener conexión nunca dispara un envío.
export function crearControlDeOperacion(generar = nuevoId) {
  let actual = null;
  let enCurso = false;
  return {
    get actual() { return actual; },
    get enCurso() { return enCurso; },
    preparar(ruta, cuerpo) {
      if (actual) return actual;
      actual = Object.freeze({ ruta, cuerpo: Object.freeze({ ...cuerpo, id: generar() }), clave: generar() });
      return actual;
    },
    comenzar() {
      if (enCurso || !actual) return null;
      enCurso = true;
      return actual;
    },
    finalizar(error) {
      enCurso = false;
      if (!error || (error.estadoHttp !== 0 && error.estadoHttp < 500 && error.codigo !== "solicitud_en_curso")) actual = null;
    },
    descartar() {
      if (enCurso) throw new Error("Esperá a que termine la solicitud.");
      actual = null;
    },
  };
}

export async function cerrarSesion(pedir) {
  return pedir("/api/sesion", { metodo: "DELETE" });
}
