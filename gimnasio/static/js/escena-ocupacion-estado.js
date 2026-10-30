// Sin GPU, cada sombra se calcula en la CPU y compite con el resto de la pantalla.
export function esDibujoPorSoftware(renderizador) {
  return /swiftshader|llvmpipe|softpipe|software|basic render/i.test(renderizador ?? '');
}

// Solo la identidad y la zona de la sede explican desplazamientos.
export function diferenciarVisitas(anteriores, actuales) {
  const antes = new Map(anteriores.map(visita => [visita.id, visita]));
  const ahora = new Map(actuales.map(visita => [visita.id, visita]));
  return {
    entradas: actuales.filter(visita => !antes.has(visita.id)),
    salidas: anteriores.filter(visita => !ahora.has(visita.id)),
    cambios: actuales.filter(visita => antes.has(visita.id) && antes.get(visita.id).zona !== visita.zona),
  };
}
