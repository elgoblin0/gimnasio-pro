import { llamarApi } from "@comun/api.js";
import { registrarPwa } from "@comun/pwa.js";

registrarPwa();

const NOMBRES_DE_ROL = {
  socio: "Socio",
  recepcion: "Recepción",
  entrenador: "Entrenador",
  administracion: "Administración",
};

const $ = (selector) => document.querySelector(selector);

// Quien trabaja con una sola pantalla entra directamente a ella.
const PANTALLA_INICIAL = { entrenador: "/bandeja.html", administracion: "/equipos.html" };

function mostrarBienvenida(usuario) {
  if (PANTALLA_INICIAL[usuario.rol]) {
    location.replace(PANTALLA_INICIAL[usuario.rol]);
    return;
  }
  $("[data-ingreso]").hidden = true;
  $("[data-bienvenida]").hidden = false;
  $("[data-saludo]").textContent = `Hola, ${usuario.nombre}`;
  $("[data-rol-actual]").textContent = NOMBRES_DE_ROL[usuario.rol] + (usuario.es_demo ? " · demo" : "");
  const recorrido = $("[data-recorrido]");
  recorrido.hidden = !["recepcion", "socio"].includes(usuario.rol);
  recorrido.href = usuario.rol === "socio" ? "/entrenamiento.html" : "/recepcion.html";
  recorrido.textContent = usuario.rol === "socio" ? "Ver mi entrenamiento" : "Ir a recepción";
}

function mostrarIngreso(modoDemo) {
  $("[data-bienvenida]").hidden = true;
  $("[data-ingreso]").hidden = false;
  $("[data-demo]").hidden = !modoDemo;
}

async function iniciar() {
  const estado = await llamarApi("/api/estado");
  $("[data-estado]").textContent = estado.modo_demo ? "Modo demo: datos ficticios que se reinician cada día." : "";
  const { usuario } = await llamarApi("/api/sesion");
  if (usuario) mostrarBienvenida(usuario);
  else mostrarIngreso(estado.modo_demo);

  $("[data-formulario-ingreso]").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.target));
    try {
      mostrarBienvenida((await llamarApi("/api/sesion", { metodo: "POST", cuerpo: datos })).usuario);
    } catch (error) {
      $("[data-error-ingreso]").textContent = error.message;
    }
  });
  for (const boton of document.querySelectorAll("[data-rol]")) {
    boton.addEventListener("click", async () => {
      try {
        const respuesta = await llamarApi(`/api/sesion/demo/${boton.dataset.rol}`, { metodo: "POST" });
        mostrarBienvenida(respuesta.usuario);
      } catch (error) {
        $("[data-error-ingreso]").textContent = error.message;
      }
    });
  }
  $("[data-salir]").addEventListener("click", async () => {
    try {
      await llamarApi("/api/sesion", { metodo: "DELETE" });
      mostrarIngreso(estado.modo_demo);
    } catch (error) {
      $("[data-estado]").textContent = error.message;
    }
  });
}

iniciar().catch((error) => {
  $("[data-estado]").textContent = error.message;
});
