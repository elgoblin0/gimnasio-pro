import { llamarApi } from "./api.js";

// La previsión cambia despacio y es la lectura más cara: cada registro de una pantalla no la vuelve a pedir.
const VIGENCIA_MS = 10 * 60_000;
let consultada = null;

export async function actualizarMejoresHorarios() {
  const bloque = document.querySelector("[data-mejores-horarios]");
  bloque.hidden = false;
  if (consultada !== null && Date.now() - consultada < VIGENCIA_MS) return;
  const anterior = consultada;
  consultada = Date.now();
  try {
    const datos = await llamarApi("/api/mejores-horarios");
    for (const [clave, nombre] of [["hoy", "Hoy"], ["manana", "Mañana"]]) {
      const dia = datos[clave];
      const destino = bloque.querySelector(`[data-horarios-${clave}]`);
      const titulo = document.createElement("h3");
      titulo.textContent = nombre;
      destino.replaceChildren(titulo);
      if (dia.cerrado || dia.datos_insuficientes || !dia.franjas.length) {
        const estado = document.createElement("p");
        estado.textContent = dia.cerrado ? "Cerrado" : (dia.datos_insuficientes ? "Datos insuficientes" : "No quedan franjas abiertas hoy.");
        destino.append(estado);
      } else {
        const lista = document.createElement("ul");
        for (const franja of dia.franjas) {
          const elemento = document.createElement("li");
          elemento.textContent = `${franja.desde.slice(0, 2)}–${franja.hasta.slice(0, 2)} · tranquilo`;
          lista.append(elemento);
        }
        destino.append(lista);
      }
    }
    bloque.querySelector("[data-horarios-estado]").textContent = "";
  } catch (error) {
    consultada = anterior;
    bloque.querySelector("[data-horarios-estado]").textContent = `No se pudieron cargar los mejores horarios. ${error.message}`;
  }
}
