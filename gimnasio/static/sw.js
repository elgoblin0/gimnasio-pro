// ADR 0007: solo recursos públicos. Cada pantalla nueva actualiza la lista y VERSION.
const VERSION = "52";
const PREFIJO_CACHE = "gimnasio-estaticos-";
const CACHE = PREFIJO_CACHE + VERSION;
const RECURSOS_ESTATICOS = [
  "/js/salud.js",
  "/js/clases.js",
  "/js/plantillas.js",
  "/estilos/ficha.css",
  "/js/ficha.js",
  "/js/perfil-entrenamiento.js",
  "/js/pagos.js",
  "/js/tipos-membresia.js",
  "/estilos/pagos.css",
  "/js/administracion.js",
  "/estilos/administracion.css",
  "/estilos/escena-ocupacion.css",
  "/js/escena-ocupacion.js",
  "/js/escena-ocupacion-estado.js",
  "/js/escena-ocupacion-plano.js",
  "/js/escena-ocupacion-maqueta.js",

  "/js/comun/sondeo.js",
  "/js/comun/horarios.js",
  "/estilos/entrenador.css",
  "/js/bandeja.js",
  "/js/bandeja-textos.js",
  "/js/comun/personal.js",
  "/js/equipos.js",
  "/js/equipos-datos.js",
  "/js/comun/volumen-zonas.js",
  "/js/editor-programa.js",
  "/js/editor-programa-datos.js",
  "/manifest.webmanifest",
  "/iconos/gimnasio-192.png",
  "/iconos/gimnasio-512.png",
  "/iconos/gimnasio-maskable-512.png",
  "/estilos/tokens.css",
  "/estilos/base.css",
  "/estilos/recorrido.css",
  "/js/recepcion.js",
  "/js/entrenamiento.js",
  "/js/resumen-sesion.js",
  "/js/comun/progreso.js",
  "/js/comun/zonas.js",
  "/js/comun/sustituciones.js",
  "/js/comun/operaciones.js",
  "/js/comun/series.js",
  "/js/comun/descanso.js",
  "/js/inicio.js",
  "/js/comun/api.js",
  "/js/comun/pwa.js",
  "/js/comun/formatos.js",
  "/js/comun/ids.js",
  "/js/comun/reloj.js",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(
    RECURSOS_ESTATICOS.map((ruta) => new Request(ruta, { cache: "reload", credentials: "omit" })),
  )));
  // Sin skipWaiting: una actualización espera al cierre de las ventanas en uso.
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil((async () => {
    for (const nombre of await caches.keys()) {
      if (nombre.startsWith(PREFIJO_CACHE) && nombre !== CACHE) await caches.delete(nombre);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (evento) => {
  const solicitud = evento.request;
  const url = new URL(solicitud.url);
  const esEstatico = solicitud.method === "GET" && url.origin === self.location.origin
    && !url.search && RECURSOS_ESTATICOS.includes(url.pathname);

  if (esEstatico) {
    evento.respondWith(caches.open(CACHE).then(async (cache) =>
      (await cache.match(solicitud)) ?? fetch(solicitud, { cache: "no-store" })));
    return;
  }

  // API, escrituras, HTML y cualquier recurso ajeno a la lista: siempre a red.
  evento.respondWith(fetch(solicitud, { cache: "no-store" }).catch((error) => {
    if (solicitud.mode !== "navigate") throw error;
    return new Response(`<!doctype html><html lang="es"><meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Gimnasio Pro · Conexión requerida</title><main><h1>Conexión requerida</h1>
      <p>Gimnasio Pro requiere conexión a Internet. No se pudo conectar con el servidor.</p>
      <p>Volvé a abrir la página cuando tengas conexión.</p></main></html>`, {
      status: 503,
      headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
    });
  }));
});
