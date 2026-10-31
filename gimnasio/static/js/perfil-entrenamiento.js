import { llamarApi } from "./comun/api.js";
import { crear } from "./comun/personal.js";

export const FINALIDAD_PERFIL = "Usamos tu perfil para que tu entrenador arme tu programa. No escribas datos de salud acá: van en tu ficha de salud.";
const lecturas = new WeakMap();

export function datosDelPerfil(formulario) {
  return Object.fromEntries([...new FormData(formulario)].map(([campo, valor]) => [campo,
    valor === "" ? null : ["disponibilidad_semanal", "tiempo_por_sesion"].includes(campo) ? Number(valor) : valor,
  ]));
}

export async function montarPerfil(contenedor, ruta) {
  const lectura = {};
  lecturas.set(contenedor, lectura);
  const estado = crear("p", { role: "status" }, "Cargando perfil de entrenamiento…");
  const error = crear("p", { role: "alert" });
  contenedor.replaceChildren(crear("h2", {}, "Perfil de entrenamiento"), estado, error);
  try {
    const { perfil_entrenamiento: perfil } = await llamarApi(ruta);
    if (lecturas.get(contenedor) !== lectura) return;
    const formulario = crear("form", {}, crear("p", {}, FINALIDAD_PERFIL));
    for (const [campo, etiqueta, propiedades] of [
      ["objetivo", "Objetivo", { type: "text", maxLength: 500 }],
      ["experiencia", "Experiencia", null],
      ["disponibilidad_semanal", "Disponibilidad semanal (días)", { type: "number", min: 1, max: 7, step: 1 }],
      ["tiempo_por_sesion", "Tiempo por sesión (minutos)", { type: "number", min: 15, max: 240, step: 1 }],
      ["preferencias", "Preferencias", { type: "text", maxLength: 500 }],
    ]) {
      const entrada = propiedades ? crear("input", { name: campo, ...propiedades })
        : crear("select", { name: campo }, [
          ["", "Sin indicar"], ["inicial", "Inicial"], ["intermedia", "Intermedia"], ["avanzada", "Avanzada"],
        ].map(([valor, texto]) => crear("option", { value: valor }, texto)));
      entrada.value = perfil[campo] ?? "";
      formulario.append(crear("label", {}, etiqueta, entrada));
    }
    const boton = crear("button", { type: "submit" }, "Guardar perfil de entrenamiento");
    formulario.append(boton);
    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      boton.disabled = true;
      estado.textContent = "Guardando…";
      error.textContent = "";
      try {
        const campos = datosDelPerfil(formulario);
        await llamarApi(ruta, { metodo: "PUT", cuerpo: ruta === "/api/yo/ficha" ? { perfil_entrenamiento: campos } : campos });
        estado.textContent = "Perfil de entrenamiento guardado.";
      } catch (problema) {
        estado.textContent = "";
        error.textContent = problema.message;
      } finally { boton.disabled = false; }
    });
    estado.textContent = Object.values(perfil).every((valor) => valor === null)
      ? "Todavía no hay un perfil de entrenamiento. Todos los campos son opcionales." : "";
    contenedor.append(formulario);
  } catch (problema) {
    if (lecturas.get(contenedor) !== lectura) return;
    estado.textContent = "";
    error.textContent = problema.message;
    const reintentar = crear("button", { type: "button" }, "Reintentar");
    reintentar.addEventListener("click", () => montarPerfil(contenedor, ruta));
    contenedor.append(reintentar);
  }
}
