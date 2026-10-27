// Una actualización nunca recarga la página ni descarta formularios en curso.
export async function registrarPwa() {
  if (!("serviceWorker" in navigator)) return;
  try {
    const registro = await navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" });
    const avisar = () => {
      if (!registro.waiting || !navigator.serviceWorker.controller) return;
      const aviso = document.querySelector("[data-actualizacion]");
      if (aviso) aviso.hidden = false;
    };
    avisar();
    registro.addEventListener("updatefound", () => {
      registro.installing?.addEventListener("statechange", avisar);
    });
  } catch {
    const aviso = document.querySelector("[data-estado-pwa]");
    if (aviso) aviso.textContent = "No se pudo preparar la instalación. Se requiere conexión a Internet.";
  }
}
