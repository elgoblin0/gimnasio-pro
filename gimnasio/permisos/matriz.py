"""Matriz de permisos por rol (ADR 0006). Es la única fuente de qué puede hacer cada rol.

Los alcances finos (el entrenador solo ve a sus socios asignados, el socio solo lo suyo)
los aplica cada servicio. Acá solo se decide si el rol puede intentar la acción.
"""

ROLES = ("socio", "recepcion", "entrenador", "administracion")

PERMISOS = {
    "socios.editar_datos_propios": {"socio"},
    "socios.editar_datos": {"recepcion", "administracion"},
    # Propios del socio
    "entrenamiento.ver_propio": {"socio"},
    "entrenamiento.registrar_propio": {"socio"},
    "salud.ver_propia": {"socio"},
    "consentimientos.gestionar_propios": {"socio"},
    # Recepción
    "ocupacion.ver": set(ROLES),
    "visitas.ver": {"recepcion"},
    "visitas.registrar": {"recepcion"},
    "socios.ver_tarjeta": {"recepcion", "administracion"},
    "pagos.registrar": {"recepcion", "administracion"},
    "clases.gestionar_reservas": {"recepcion"},
    # Entrenador
    "entrenamiento.ver_asignados": {"entrenador"},
    "socios.ver_asignados": {"entrenador"},
    "avisos.revisar": {"entrenador"},
    "salud.ver_asignados": {"entrenador"},
    "programas.editar": {"entrenador"},
    "alternativas.editar": {"entrenador", "administracion"},
    "equipos.gestionar": {"entrenador", "administracion"},
    # Administración
    "configuracion.editar": {"administracion"},
    "usuarios.administrar": {"administracion"},
}


def puede(rol, permiso):
    if rol not in ROLES:
        raise ValueError(f"rol desconocido: {rol!r}")
    if permiso not in PERMISOS:
        raise ValueError(f"permiso desconocido: {permiso!r}")
    return rol in PERMISOS[permiso]
