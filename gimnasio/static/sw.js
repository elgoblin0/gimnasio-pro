// ADR 0007: solo recursos públicos. Cada pantalla nueva actualiza la lista y VERSION.
const VERSION = "1";
const PREFIJO_CACHE = "gimnasio-estaticos-";
const CACHE = PREFIJO_CACHE + VERSION;
const RECURSOS_ESTATICOS = [
  "/manifest.webmanifest",
  "/iconos/gimnasio-192.png",
  "/iconos/gimnasio-512.png",
  "/iconos/gimnasio-maskable-512.png",
  "/estilos/tokens.css",
  "/estilos/base.css",
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
