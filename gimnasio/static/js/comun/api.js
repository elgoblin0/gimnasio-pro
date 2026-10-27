// Cliente de la API. Toda llamada pasa por acá: agrega el encabezado anti-CSRF (ADR 0006)
// y una clave de idempotencia en los métodos que cambian algo (ADR 0004).

const METODOS_QUE_CAMBIAN = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ErrorDeApi extends Error {
  constructor(codigo, mensaje, estadoHttp) {
    super(mensaje);
    this.codigo = codigo;
    this.estadoHttp = estadoHttp;
  }
}

/**
 * @param {{fetch?: typeof fetch, nuevaClave?: () => string}} dependencias
 */
export function crearApi({ fetch: pedir = globalThis.fetch, nuevaClave = () => crypto.randomUUID() } = {}) {
  return async function llamarApi(ruta, { metodo = "GET", cuerpo, clave } = {}) {
    const encabezados = { Accept: "application/json" };
    if (METODOS_QUE_CAMBIAN.has(metodo)) {
      encabezados["X-Gimnasio"] = "1";
      encabezados["Idempotency-Key"] = clave ?? nuevaClave();
    }
    if (cuerpo !== undefined) encabezados["Content-Type"] = "application/json";
    const respuesta = await pedir(ruta, {
      method: metodo,
      headers: encabezados,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      credentials: "same-origin",
    });
    const datos = respuesta.status === 204 ? null : await respuesta.json();
    if (!respuesta.ok) {
      const error = datos?.error ?? {};
      throw new ErrorDeApi(error.codigo ?? "error", error.mensaje ?? "Error inesperado", respuesta.status);
    }
    return datos;
  };
}

export const llamarApi = crearApi();
