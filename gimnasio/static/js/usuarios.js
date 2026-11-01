import { llamarApi } from "@comun/api.js";
import { crear } from "@comun/personal.js";
import { formatearCedula } from "@comun/formatos.js";

const nombresRol = { socio: "Socio", recepcion: "Recepción", entrenador: "Entrenador", administracion: "Administración" };
const nombresCampos = { nombre: "Nombre", apellido: "Apellido", cedula: "Cédula", telefono: "Teléfono", correo: "Correo", fecha_nacimiento: "Fecha de nacimiento" };

export async function prepararUsuarios() {
  const panel = document.querySelector("#usuarios");
  const estado = crear("p", { role: "status", "aria-live": "polite" });
  const error = crear("p", { role: "alert" });
  const entrega = crear("p", { role: "status" });
  const lista = crear("ul", { "data-usuarios-lista": "" });
  const sinEntrenador = crear("ul", { "data-sin-entrenador": "" });
  let pagina = 1;
  const consulta = crear("input", { name: "q", type: "search", maxLength: 160 });
  const rol = crear("select", { name: "rol" }, ...["", "socio", "recepcion", "entrenador", "administracion"].map((valor) => crear("option", { value: valor }, nombresRol[valor] || "Todos")));
  const activo = crear("select", { name: "activo" }, crear("option", { value: "" }, "Todos"), crear("option", { value: "true" }, "Activos"), crear("option", { value: "false" }, "Inactivos"));
  const anterior = crear("button", { type: "button", onclick: () => { pagina--; cargar(); } }, "Página anterior");
  const siguiente = crear("button", { type: "button", onclick: () => { pagina++; cargar(); } }, "Página siguiente");

  function mostrarClave(datos) {
    entrega.textContent = datos.clave_provisional
      ? `Clave provisional (se muestra una sola vez): ${datos.clave_provisional}. Debe cambiarla al ingresar.`
      : datos.clave_ya_entregada ? "La clave ya se entregó. Si se perdió, restablecela con una nueva solicitud." : "Usuario creado en modo demo, sin clave.";
  }

  async function ejecutar(boton, ruta, metodo, cuerpo) {
    boton.disabled = true;
    error.textContent = "";
    estado.textContent = "Guardando…";
    const huella = JSON.stringify([ruta, cuerpo]);
    if (boton.dataset.huella !== huella) {
      boton.dataset.huella = huella;
      boton.dataset.clave = crypto.randomUUID();
    }
    try {
      const datos = await llamarApi(ruta, { metodo, cuerpo, clave: boton.dataset.clave });
      delete boton.dataset.huella;
      mostrarClave(datos);
      await cargar();
      return true;
    } catch (fallo) {
      error.textContent = fallo.message;
      estado.textContent = "";
      return false;
    } finally { boton.disabled = false; }
  }

  function asignacion(usuario) {
    const entrenador = crear("select", { required: true, "aria-label": `Entrenador de ${usuario.nombre} ${usuario.apellido}` }, crear("option", { value: "" }, "Elegir entrenador"));
    const boton = crear("button", { type: "submit", className: "boton-borde" }, "Asignar entrenador");
    const formulario = crear("form", { onsubmit: async (evento) => {
      evento.preventDefault();
      if (await ejecutar(boton, `/api/socios/${usuario.id}/entrenador`, "PUT", { entrenador_id: entrenador.value })) entrega.textContent = "Entrenador asignado.";
    } }, entrenador, boton);
    // El selector se carga una sola vez para todos los socios, incluso con más de 50 entrenadores.
    for (const persona of entrenadores) entrenador.append(crear("option", { value: persona.id }, `${persona.nombre} ${persona.apellido}`));
    return formulario;
  }

  function cambioEstado(usuario) {
    const accion = usuario.activo ? "Desactivar" : "Reactivar";
    const boton = crear("button", { type: "button", className: "boton-borde", onclick: () => {
      const revocacion = crear("input", { type: "checkbox" });
      const confirmar = crear("button", { type: "submit", className: "boton-tinta" }, accion);
      const cancelar = crear("button", { type: "button", onclick: () => dialogo.close() }, "Cancelar");
      const formulario = crear("form", { onsubmit: async (evento) => {
        evento.preventDefault();
        cancelar.disabled = true;
        const cuerpo = usuario.activo ? { por_revocacion: revocacion.checked } : {};
        if (await ejecutar(confirmar, `/api/usuarios/${usuario.id}/${usuario.activo ? "desactivar" : "reactivar"}`, "POST", cuerpo)) {
          entrega.textContent = `Usuario ${usuario.activo ? "desactivado" : "reactivado"}.`;
          dialogo.close();
        } else {
          rechazo.textContent = error.textContent;
        }
        cancelar.disabled = false;
      } }, crear("h3", {}, `${accion} a ${usuario.nombre} ${usuario.apellido}`),
      crear("p", {}, usuario.activo ? "Se cancelarán sus reservas futuras y se cerrarán sus asignaciones. Su historial se conserva." : "No se restaurarán reservas ni asignaciones."));
      if (usuario.activo && usuario.rol === "socio") formulario.append(crear("label", {}, revocacion, " A pedido del socio por revocación de datos personales"));
      const rechazo = crear("p", { role: "alert" });
      formulario.append(rechazo, confirmar, cancelar);
      const dialogo = crear("dialog", { "aria-label": `${accion} usuario` }, formulario);
      dialogo.addEventListener("cancel", (evento) => { if (confirmar.disabled) evento.preventDefault(); });
      dialogo.addEventListener("close", () => dialogo.remove());
      panel.append(dialogo);
      dialogo.showModal();
    } }, accion);
    return boton;
  }

  let entrenadores = [];
  async function cargar() {
    estado.textContent = "Cargando usuarios…";
    error.textContent = "";
    anterior.disabled = siguiente.disabled = true;
    try {
      const parametros = new URLSearchParams({ q: consulta.value, rol: rol.value, activo: activo.value, pagina });
      const [datos, pendientes] = await Promise.all([llamarApi(`/api/usuarios?${parametros}`), llamarApi("/api/socios/sin-entrenador")]);
      entrenadores = [];
      let numero = 1;
      let respuesta;
      do {
        respuesta = await llamarApi(`/api/usuarios?rol=entrenador&activo=true&pagina=${numero++}`);
        entrenadores.push(...respuesta.usuarios);
      } while (respuesta.hay_mas);
      lista.replaceChildren(...datos.usuarios.map((usuario) => {
        const restablecer = crear("button", { type: "button", className: "boton-borde", onclick: () => ejecutar(restablecer, `/api/usuarios/${usuario.id}/clave`, "POST") }, "Restablecer clave");
        return crear("li", {}, crear("p", {}, `${usuario.nombre} ${usuario.apellido} · ${formatearCedula(usuario.cedula)} · ${nombresRol[usuario.rol]} · ${usuario.activo ? "Activo" : "Inactivo"}`), restablecer, cambioEstado(usuario), ...(usuario.rol === "socio" && usuario.activo ? [asignacion(usuario)] : []));
      }));
      sinEntrenador.replaceChildren(...pendientes.socios.map((socio) => crear("li", {}, crear("p", {}, `${socio.nombre} ${socio.apellido} · ${formatearCedula(socio.cedula)}`), asignacion(socio))));
      if (!pendientes.socios.length) sinEntrenador.append(crear("li", {}, "No hay socios sin entrenador."));
      estado.textContent = datos.usuarios.length ? `Página ${pagina}` : "No hay usuarios para estos filtros.";
      anterior.disabled = pagina === 1;
      siguiente.disabled = !datos.hay_mas;
    } catch (fallo) { estado.textContent = ""; error.textContent = fallo.message; }
  }

  const filtros = crear("form", { onsubmit: (evento) => { evento.preventDefault(); pagina = 1; cargar(); } },
    crear("label", {}, "Buscar por nombre, apellido o cédula ", consulta), crear("label", {}, "Rol ", rol), crear("label", {}, "Estado ", activo), crear("button", { type: "submit" }, "Buscar"));
  const alta = crear("form");
  const campos = ["nombre", "apellido", "cedula", "telefono", "correo", "fecha_nacimiento"];
  for (const campo of campos) alta.append(crear("label", {}, `${nombresCampos[campo]} `,
    crear("input", { name: campo, type: campo === "correo" ? "email" : campo === "fecha_nacimiento" ? "date" : "text", required: ["nombre", "apellido", "cedula"].includes(campo) })));
  alta.append(crear("label", {}, "Rol ", crear("select", { name: "rol" }, ...["recepcion", "entrenador", "administracion"].map((valor) => crear("option", { value: valor }, nombresRol[valor])))));
  const guardar = crear("button", { type: "submit", className: "boton-tinta" }, "Crear personal");
  alta.append(guardar);
  alta.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (await ejecutar(guardar, "/api/usuarios", "POST", Object.fromEntries(new FormData(alta)))) alta.reset();
  });
  panel.append(estado, error, entrega, crear("button", { type: "button", onclick: cargar }, "Volver a cargar usuarios"), crear("h3", {}, "Crear personal"), alta, crear("h3", {}, "Usuarios"), filtros, lista, anterior, siguiente, crear("h3", {}, "Socios sin entrenador"), sinEntrenador);
  await cargar();
}
