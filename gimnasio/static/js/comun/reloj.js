// Único acceso al reloj del sistema en los módulos JS (ADR 0005).
export function crearReloj({ fijo } = {}) {
  const momento = fijo === undefined ? undefined : new Date(fijo).getTime();
  if (momento !== undefined && !Number.isFinite(momento)) {
    throw new RangeError("El momento fijo debe ser una fecha válida");
  }
  return {
    ahora: () => momento === undefined ? new Date() : new Date(momento),
  };
}
