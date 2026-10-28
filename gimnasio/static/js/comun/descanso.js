// Hora inyectada en milisegundos; no guarda estado fuera de esta instancia.
export function crearDescanso(duracion, ahora) {
  if (!Number.isFinite(duracion) || duracion < 0) throw new RangeError("El descanso debe ser positivo o cero.");
  let fin = Number(ahora) + duracion * 1000;
  return {
    consultar(momento) {
      const restantes = Math.max(0, Math.ceil((fin - Number(momento)) / 1000));
      return { restantes, terminado: restantes === 0 };
    },
    saltear(momento) { fin = Number(momento); },
    sumar30(momento) { fin = Math.max(fin, Number(momento)) + 30000; },
  };
}
