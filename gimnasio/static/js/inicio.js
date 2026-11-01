import { llamarApi } from "@comun/api.js";
import { registrarPwa } from "@comun/pwa.js";
import { crear } from "@comun/personal.js";
import { textoDia, textosDeHitos } from "./acompanamiento-textos.js";

registrarPwa();

const NOMBRES_DE_ROL = {
  socio: "Socio",
  recepcion: "Recepción",
  entrenador: "Entrenador",
  administracion: "Administración",
};

const $ = (selector) => document.querySelector(selector);

// Quien trabaja con una sola pantalla entra directamente a ella.
const PANTALLA_INICIAL = { entrenador: "/bandeja.html", administracion: "/administracion.html" };

function mostrarBienvenida(usuario) {
  if (usuario.debe_cambiar_clave) {
    location.replace("/clave.html");
    return;
  }
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
  $("[data-mi-ficha]").hidden = usuario.rol !== "socio";
  $("[data-avisos]").hidden = usuario.rol !== "socio";
  $("[data-incorporacion]").hidden = true;
  if (usuario.rol === "socio") {
    cargarAvisos();
    cargarIncorporacion();
  }
}

async function cargarIncorporacion() {
  try {
    const { incorporacion } = await llamarApi("/api/yo/incorporacion");
    $("[data-incorporacion]").hidden = !incorporacion;
    if (!incorporacion) return;
    $("[data-incorporacion-dia]").textContent = textoDia(incorporacion.dia);
    $("[data-incorporacion-hitos]").replaceChildren(...textosDeHitos(incorporacion.hitos).map(({ texto, cumplido }) =>
      crear("li", { "data-cumplido": String(cumplido) }, `${cumplido ? "✓" : "○"} ${texto}`)));
  } catch {
    // La incorporación acompaña al inicio: si falla, el resto de la pantalla sigue sirviendo.
    $("[data-incorporacion]").hidden = true;
  }
}

const textosAviso = {
  paso_a_tener_lugar: "Pasaste a tener lugar",
  volvio_a_espera: "Volviste a la lista de espera",
  ocurrencia_cancelada: "Se canceló la ocurrencia",
};

async function cargarAvisos() {
  const estado = $("[data-avisos-estado]");
  const lista = $("[data-avisos-lista]");
  estado.textContent = "Cargando avisos al socio…";
  lista.replaceChildren();
  try {
    const { avisos } = await llamarApi("/api/yo/avisos");
    estado.textContent = avisos.length ? "" : "No tenés avisos sin ver.";
    lista.replaceChildren(...avisos.map((aviso) => {
      const clave = crypto.randomUUID();
      const boton = crear("button", { type: "button", onclick: async () => {
        boton.disabled = true;
        try {
          await llamarApi(`/api/yo/avisos/${aviso.id}/visto`, { metodo: "POST", clave });
          await cargarAvisos();
        } catch (error) {
          estado.textContent = error.message;
          boton.disabled = false;
        }
      } }, "Marcar como visto");
      return crear("li", {}, `${textosAviso[aviso.tipo]} · ${aviso.clase} · ${aviso.fecha.split("-").reverse().join("/")} ${aviso.hora_inicio} `, boton);
    }));
  } catch (error) {
    estado.textContent = error.message;
  }
}

function mostrarIngreso(modoDemo) {
  $("[data-bienvenida]").hidden = true;
  $("[data-ingreso]").hidden = false;
  $("[data-demo]").hidden = !modoDemo;
}

async function iniciar() {
  $("[data-avisos-reintentar]").addEventListener("click", cargarAvisos);
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
  if (estado.modo_demo) {
    const { socios } = await llamarApi("/api/sesion/demo/socios");
    const lista = crear("div");
    for (const socio of socios) {
      lista.append(crear("button", { type: "button", onclick: async () => {
        try {
          mostrarBienvenida((await llamarApi("/api/sesion/demo/socio", { metodo: "POST", cuerpo: { usuario_id: socio.id } })).usuario);
        } catch (error) { $("[data-error-ingreso]").textContent = error.message; }
      } }, `Entrar como ${socio.nombre} ${socio.apellido}`));
    }
    $("[data-demo]").append(lista);
  }

}

iniciar().catch((error) => {
  $("[data-estado]").textContent = error.message;
});
