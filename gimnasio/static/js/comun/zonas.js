// Las mismas zonas del cuerpo que el motor; coordenadas de frente y espalda.
export const ZONAS_CUERPO = Object.freeze([
  ["pecho", "Pecho", "M65 85 H135 V125 H65 Z"],
  ["espalda_alta", "Espalda alta", "M225 85 H295 V115 H225 Z"],
  ["dorsales", "Dorsales", "M225 118 H243 V166 H225 Z M277 118 H295 V166 H277 Z"],
  ["hombros", "Hombros", "M45 83 L62 80 V116 H43 Z M138 80 L155 83 L157 116 H138 Z"],
  ["biceps", "Bíceps", "M43 120 H60 V160 H39 Z M140 120 H157 L161 160 H140 Z"],
  ["triceps", "Tríceps", "M203 117 H220 V164 H199 Z M300 117 H317 L321 164 H300 Z"],
  ["abdomen", "Abdomen", "M72 130 H128 V187 H72 Z"],
  ["gluteos", "Glúteos", "M226 192 H294 V229 H226 Z"],
  ["cuadriceps", "Cuádriceps", "M64 225 H96 V280 H66 Z M104 225 H136 L134 280 H104 Z"],
  ["isquiotibiales", "Isquiotibiales", "M225 234 H256 V282 H226 Z M264 234 H295 L294 282 H264 Z"],
  ["pantorrillas", "Pantorrillas", "M227 302 H255 V353 H231 Z M265 302 H293 L289 353 H265 Z"],
  ["zona_lumbar", "Zona lumbar", "M229 169 H291 V188 H229 Z"],
  ["rodillas", "Rodillas", "M66 284 H96 V302 H66 Z M104 284 H134 V302 H104 Z"],
  ["cuello", "Cuello", "M88 61 H112 V81 H88 Z"],
].map(([id, nombre, trazo]) => Object.freeze({ id, nombre, trazo })));

export function crearSelectorZonas(contenedor) {
  const documento = contenedor.ownerDocument;
  const seleccionadas = new Set();
  const svg = documento.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 530 400");
  svg.setAttribute("class", "silueta-zonas");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", "Zonas del cuerpo con dolor");
  const elemento = (nombre, atributos) => {
    const nodo = documento.createElementNS(svg.namespaceURI, nombre);
    for (const [clave, valor] of Object.entries(atributos)) nodo.setAttribute(clave, valor);
    return nodo;
  };
  for (const centro of [100, 260]) {
    const cabeza = elemento("circle", { cx: centro, cy: 39, r: 22, class: "silueta-base", "aria-hidden": "true" });
    const cuerpo = elemento("path", {
      d: `M${centro - 14} 64 L${centro - 55} 82 L${centro - 67} 192 L${centro - 49} 196 L${centro - 34} 132 L${centro - 35} 222 L${centro - 28} 374 H${centro - 5} L${centro} 243 L${centro + 5} 374 H${centro + 28} L${centro + 35} 222 L${centro + 34} 132 L${centro + 49} 196 L${centro + 67} 192 L${centro + 55} 82 L${centro + 14} 64 Z`,
      class: "silueta-base", "aria-hidden": "true",
    });
    svg.append(cabeza, cuerpo);
  }
  const controles = ZONAS_CUERPO.map((zona, indice) => {
    const control = elemento("g", { role: "checkbox", tabindex: "0", "aria-label": zona.nombre, "aria-checked": "false", "data-zona": zona.id });
    const region = elemento("path", { d: zona.trazo, class: "silueta-region" });
    const nombre = elemento("text", { x: 340, y: 30 + indice * 26 });
    nombre.textContent = zona.nombre;
    control.append(region, nombre);
    const cambiar = () => {
      if (control.getAttribute("aria-disabled") === "true") return;
      if (seleccionadas.has(zona.id)) seleccionadas.delete(zona.id);
      else seleccionadas.add(zona.id);
      control.setAttribute("aria-checked", String(seleccionadas.has(zona.id)));
    };
    control.addEventListener("click", cambiar);
    control.addEventListener("keydown", (evento) => {
      if (evento.key === " " || evento.key === "Enter") { evento.preventDefault(); cambiar(); }
    });
    svg.append(control);
    return control;
  });
  contenedor.append(svg);
  return {
    zonas: () => ZONAS_CUERPO.filter((z) => seleccionadas.has(z.id)).map((z) => z.id),
    deshabilitar(valor) {
      for (const control of controles) {
        control.setAttribute("aria-disabled", String(valor));
        control.setAttribute("tabindex", valor ? "-1" : "0");
      }
    },
  };
}
