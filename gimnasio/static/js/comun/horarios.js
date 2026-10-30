import { llamarApi } from "./api.js";

export async function actualizarMejoresHorarios() {
  const bloque = document.querySelector("[data-mejores-horarios]");
  bloque.hidden = false;
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
    bloque.querySelector("[data-horarios-estado]").textContent = `No se pudieron cargar los mejores horarios. ${error.message}`;
  }
}
