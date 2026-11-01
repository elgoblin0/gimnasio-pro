import { llamarApi } from "./comun/api.js";
import { crear, exigirRol, prepararBarra } from "./comun/personal.js";
import { registrarPwa } from "./comun/pwa.js";
import { formatearCedula, formatearFecha, formatearTelefono, formatearGuaranies } from "./comun/formatos.js";
import { montarPerfil } from "./perfil-entrenamiento.js";
import { montarSalud } from "./salud.js";
import { montarConsultasFicha } from "./consultas-ficha.js";

registrarPwa();
const $ = (selector) => document.querySelector(selector);
let usuario;

async function cargar() {
  $("[data-error]").textContent = "";
  $("[data-estado]").textContent = "Cargando ficha del socio…";
  $("[data-reintentar]").hidden = true;
  try {
    if (!usuario) {
      usuario = await exigirRol(["socio", "recepcion", "administracion"]);
      if (!usuario) return;
      prepararBarra(usuario);
    }
    const propia = usuario.rol === "socio";
    const socio = new URL(location.href).searchParams.get("socio");
    if (!propia && !socio) throw new Error("Elegí un socio desde su tarjeta contextual.");
    const ruta = propia ? "/api/yo/ficha" : `/api/socios/${encodeURIComponent(socio)}/ficha`;
    const { datos_personales: datos } = await llamarApi(ruta);
    $("[data-titulo]").textContent = propia ? "Mi ficha" : `Ficha del socio · ${datos.nombre} ${datos.apellido}`;
    $("[data-volver]").href = propia ? "/entrenamiento.html" : usuario.rol === "recepcion" ? "/recepcion.html" : "/equipos.html";
    const formulario = crear("form", {}, crear("p", {}, "Usamos los datos personales para identificar al socio y mantener el contacto con él."));
    for (const [campo, etiqueta, tipo, longitud] of [
      ["nombre", "Nombre", "text", 80], ["apellido", "Apellido", "text", 80], ["cedula", "Cédula", "text", 16],
      ["telefono", "Teléfono (+595)", "tel", 30], ["correo", "Correo", "email", 160],
      ["fecha_nacimiento", "Nacimiento", "date"],
    ]) {
      if (propia && !["telefono", "correo"].includes(campo)) {
        const texto = campo === "cedula" ? formatearCedula(datos[campo])
          : campo === "fecha_nacimiento" && datos[campo] ? formatearFecha(datos[campo]) : datos[campo];
        formulario.append(crear("p", {}, `${etiqueta}: ${texto || "Sin indicar"}`));
      } else formulario.append(crear("label", {}, etiqueta, crear("input", {
        name: campo, type: tipo, value: campo === "cedula" ? formatearCedula(datos[campo])
          : campo === "telefono" && datos[campo] ? formatearTelefono(datos[campo]) : datos[campo] ?? "", maxLength: longitud,
        required: ["nombre", "apellido", "cedula"].includes(campo),
      })));
    }
    const boton = crear("button", { type: "submit" }, "Guardar datos personales");
    formulario.append(boton);
    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      boton.disabled = true;
      $("[data-error]").textContent = "";
      $("[data-estado]").textContent = "Guardando…";
      try {
        await llamarApi(ruta, { metodo: "PUT", cuerpo: Object.fromEntries(new FormData(formulario)) });
        $("[data-estado]").textContent = "Datos personales guardados.";
      } catch (error) {
        $("[data-estado]").textContent = "";
        $("[data-error]").textContent = error.message;
      } finally { boton.disabled = false; }
    });
    $("[data-personales]").replaceChildren(crear("h2", {}, "Datos personales"), formulario);
    $("[data-personales]").hidden = false;
    $("[data-estado]").textContent = "";
    if (propia) {
      formulario.append(crear("p", {}, "Revocar el consentimiento de datos personales equivale a pedir la baja. Solicitá la baja en recepción."));
      await montarConsultasFicha($("[data-consultas-ficha]"));
      await montarPagos();
      $("[data-perfil]").hidden = false;
      await montarConsentimiento();
      await montarPerfil($("[data-perfil]"), ruta);
      $("[data-salud]").hidden = false;
      await montarSalud($("[data-salud]"));
    }
  } catch (error) {
    $("[data-estado]").textContent = "";
    $("[data-error]").textContent = error.message;
    $("[data-reintentar]").hidden = false;
  }
}
$("[data-reintentar]").addEventListener("click", cargar);
cargar();

async function montarPagos() {
  const contenedor = $("[data-membresia-pagos]");
  contenedor.hidden = false;
  contenedor.textContent = "Cargando membresía y pagos…";
  const { membresia, pagos } = await llamarApi("/api/yo/pagos");
  const estado = membresia.vigente ? `Vigente hasta ${formatearFecha(membresia.hasta)} · ${membresia.dias_restantes} días restantes.` : "Sin membresía vigente.";
  contenedor.replaceChildren(crear("h2", {}, "Mi membresía y pagos"), crear("p", {}, estado));
  if (!pagos.length) contenedor.append(crear("p", {}, "Todavía no tenés pagos registrados."));
  for (const pago of pagos) {
    const fecha = new Intl.DateTimeFormat("es-PY", { timeZone: "America/Asuncion", day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(pago.registrado_en));
    contenedor.append(crear("p", {}, `${fecha} · ${pago.tipo} · ${pago.medio} · ${formatearGuaranies(pago.monto)}${pago.anulacion ? ` · Anulado: ${pago.anulacion.motivo}` : ""}`));
  }
}

async function montarConsentimiento() {
  const contenedor = $("[data-consentimientos]");
  contenedor.hidden = false;
  contenedor.textContent = "Cargando consentimiento…";
  const { salud } = await llamarApi("/api/yo/consentimientos");
  mostrarConsentimiento(contenedor, salud);
}

function mostrarConsentimiento(contenedor, salud) {
  const estado = crear("p", { role: "status" }, salud.otorgado ? "Consentimiento otorgado." : "Sin consentimiento de salud vigente.");
  const boton = crear("button", { type: "button" }, salud.otorgado ? "Revocar consentimiento de salud" : "Otorgar consentimiento de salud");
  contenedor.replaceChildren(crear("h2", {}, "Consentimiento de salud"), crear("p", {}, salud.texto), estado, boton);
  let clave;
  boton.addEventListener("click", async () => {
    if (salud.otorgado && !window.confirm("Al revocar, tus restricciones dejan de protegerte y no tendrás subas. ¿Confirmás la revocación de salud?")) return;
    boton.disabled = true;
    estado.textContent = "Guardando consentimiento…";
    clave ??= crypto.randomUUID();
    try {
      const { salud: actualizado } = await llamarApi("/api/yo/consentimientos/salud", {
        metodo: "POST", clave, cuerpo: { otorgado: !salud.otorgado, version_texto: salud.version_texto },
      });
      mostrarConsentimiento(contenedor, actualizado);
      if (typeof montarSalud === "function") montarSalud($("[data-salud]"));
    } catch (error) {
      estado.textContent = error.message;
      boton.disabled = false;
    }
  });
}
