// Menú único por rol de la cabecera. Es un script clásico dentro del <nav> para dibujarlo antes del primer
// pintado, con la sesión que recuerda este navegador; comun/api.js la mantiene al día con cada respuesta de
// /api/sesion. Un script clásico no puede exportar: lo público queda en globalThis.menuGimnasio.

(() => {
  const CLAVE_SESION = "gimnasio-sesion-menu";
  const CLASES = { texto: "Clases", href: "/clases.html" };

  // `incluye`: pantallas sin lugar propio en el menú de ese rol, que marcan esta sección como activa.
  const MENUS = {
    socio: [
      { texto: "Mi entrenamiento", href: "/entrenamiento.html", incluye: ["/resumen-sesion.html"] },
      CLASES,
      { texto: "Mi ficha", href: "/ficha.html" },
    ],
    recepcion: [
      { texto: "Recepción", href: "/recepcion.html", incluye: ["/ficha.html"] },
      { texto: "Pagos", href: "/pagos.html" },
      CLASES,
    ],
    entrenador: [
      { texto: "Bandeja", href: "/bandeja.html", incluye: ["/editor-programa.html"] },
      { texto: "Equipos", href: "/equipos.html" },
      CLASES,
    ],
    administracion: [
      {
        texto: "Administración",
        href: "/administracion.html",
        incluye: ["/pagos.html", "/equipos.html", "/plantillas.html", "/editor-programa.html", "/ficha.html"],
      },
      CLASES,
    ],
  };

  /** Las entradas del rol; `actual` es el valor de aria-current: "page" en su pantalla, "true" en una incluida. */
  function entradasDelMenu(rol, ruta) {
    return (MENUS[rol] ?? []).map(({ texto, href, incluye = [] }) => ({
      texto,
      href,
      actual: ruta === href ? "page" : incluye.includes(ruta) ? "true" : null,
    }));
  }

  function dibujarMenu(nav, rol, ruta) {
    nav.dataset.rol = rol ?? "";
    nav.replaceChildren(...entradasDelMenu(rol, ruta).map(({ texto, href, actual }) => {
      const enlace = nav.ownerDocument.createElement("a");
      enlace.href = href;
      enlace.textContent = texto;
      enlace.setAttribute("data-texto", texto);
      if (actual) enlace.setAttribute("aria-current", actual);
      return enlace;
    }));
  }

  function leerSesion(almacen = globalThis.localStorage) {
    try {
      const sesion = JSON.parse(almacen.getItem(CLAVE_SESION));
      return MENUS[sesion?.rol] ? sesion : null;
    } catch {
      return null;
    }
  }

  function aplicar(sesion) {
    if (typeof document === "undefined") return;
    // El aviso de la demo queda decidido desde el primer pintado: aparecer después movería la cabecera.
    if (sesion) document.documentElement.dataset.sesionDemo = sesion.demo ? "si" : "no";
    else delete document.documentElement.dataset.sesionDemo;
    for (const nav of document.querySelectorAll("nav[data-menu]")) {
      if (nav.dataset.rol !== (sesion?.rol ?? "")) dibujarMenu(nav, sesion?.rol, location.pathname);
    }
  }

  /** Recuerda la persona con sesión (o ninguna) y corrige el menú si cambió. */
  function sincronizarSesion(usuario, almacen = globalThis.localStorage) {
    const sesion = MENUS[usuario?.rol] ? { rol: usuario.rol, demo: Boolean(usuario.es_demo) } : null;
    try {
      if (sesion) almacen.setItem(CLAVE_SESION, JSON.stringify(sesion));
      else almacen.removeItem(CLAVE_SESION);
    } catch { /* Sin almacenamiento, el menú se pide en cada pantalla. */ }
    aplicar(sesion);
  }

  globalThis.menuGimnasio = { entradasDelMenu, dibujarMenu, leerSesion, sincronizarSesion };

  // Importado desde api.js no hay nada que montar: `currentScript` solo existe en el script clásico del <nav>.
  const guion = globalThis.document?.currentScript;
  if (!guion) return;
  guion.parentElement.dataset.menu = "";
  const sesion = leerSesion();
  aplicar(sesion);
  if (sesion) return;
  // Primera vez en este navegador: el lugar del menú ya está reservado (estilos/base.css) y se llena al responder.
  fetch("/api/sesion", { headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store" })
    .then((respuesta) => respuesta.json())
    .then(({ usuario }) => sincronizarSesion(usuario))
    .catch(() => {});
})();
