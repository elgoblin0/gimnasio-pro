"""Acceso por rol, "entrar como…" en modo demo y consentimientos (ADR 0006). Ruta sensible."""

from contextlib import contextmanager
from datetime import timedelta
from functools import cache, wraps

from flask import current_app, g, session
from werkzeug.security import check_password_hash, generate_password_hash

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.formatos import normalizar_cedula
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.permisos import repositorio
from gimnasio.permisos.matriz import ROLES, puede

VENTANA_DE_INTENTOS = timedelta(minutes=15)
MAX_FALLIDOS_POR_USUARIO = 5
SEGUNDOS_DE_ESPERA_DEL_CANDADO = 10
MAX_FALLIDOS_POR_IP = 20
LARGO_MINIMO_DE_CLAVE = 8
TIPOS_DE_CONSENTIMIENTO = ("datos_personales", "salud", "imagen")


@cache
def _hash_de_relleno():
    # Se verifica aunque el usuario no exista, para no revelar por el tiempo de respuesta si existe.
    return generate_password_hash("relleno-que-nunca-coincide")


def _normalizar_identificador(texto):
    texto = (texto or "").strip()
    if "@" in texto:
        return texto.lower()[:160]
    try:
        return normalizar_cedula(texto)
    except ValueError:
        return texto[:160]


def _publico(fila):
    return {
        "id": str(desde_bytes(fila["id"])),
        "rol": fila["rol"],
        "nombre": fila["nombre"],
        "apellido": fila["apellido"],
        "es_demo": bool(fila["es_demo"]),
    }


def _abrir_sesion(fila):
    # Se descarta cualquier sesión previa para evitar la fijación de sesión.
    session.clear()
    session["usuario_id"] = str(desde_bytes(fila["id"]))
    g.usuario = _publico(fila)


def iniciar_sesion(identificador, clave, ip):
    """Valida cédula o correo y clave. Limita los fallidos por usuario (con cualquiera de sus identificadores)
    y por IP en una ventana móvil. Los ingresos simultáneos desde una IP o hacia un usuario se serializan."""
    with _candado_por_ip(ip):
        return _iniciar_sesion(identificador, clave, ip)


@contextmanager
def _candado_por_ip(ip):
    """Candado con nombre de MySQL por IP: cuenta y registro de fallidos de una IP no se intercalan.

    Se toma y se suelta en transacciones aparte, para que la transacción del ingreso empiece después
    de tenerlo y su primera lectura consistente vea los intentos ya confirmados por otros.
    """
    nombre = f"gimnasio:ingreso:{ip}"[:64]
    with transaccion() as cursor:
        obtenido = repositorio.adquirir_candado(cursor, nombre, SEGUNDOS_DE_ESPERA_DEL_CANDADO)
    if not obtenido:
        raise ErrorDeDominio("ocupado", "Hay demasiados ingresos en curso. Probá de nuevo en unos segundos.", 503)
    try:
        yield
    finally:
        with transaccion() as cursor:
            repositorio.liberar_candado(cursor, nombre)


def _iniciar_sesion(identificador, clave, ip):
    reloj = reloj_actual()
    ahora = reloj.ahora()
    normalizado = _normalizar_identificador(identificador)
    with transaccion() as cursor:
        if "@" in normalizado:
            fila = repositorio.buscar_para_ingreso(cursor, correo=normalizado)
        else:
            fila = repositorio.buscar_para_ingreso(cursor, cedula=normalizado)
        usuario_id = fila["id"] if fila else None
        por_cuenta, por_ip = repositorio.contar_fallidos_desde(
            cursor, usuario_id, normalizado, ip, ahora - VENTANA_DE_INTENTOS
        )
        bloqueado = por_cuenta >= MAX_FALLIDOS_POR_USUARIO or por_ip >= MAX_FALLIDOS_POR_IP
        exitoso = False
        if not bloqueado:
            hash_guardado = fila["clave_hash"] if fila and fila["clave_hash"] else _hash_de_relleno()
            coincide = check_password_hash(hash_guardado, clave or "")
            exitoso = bool(fila and fila["clave_hash"] and fila["activo"] and coincide)
            repositorio.insertar_intento(cursor, nuevo_id(reloj), usuario_id, normalizado, ip, exitoso, ahora)
    if bloqueado:
        raise ErrorDeDominio("demasiados_intentos", "Demasiados intentos fallidos. Probá de nuevo en 15 minutos.", 429)
    if not exitoso:
        raise ErrorDeDominio("credenciales_invalidas", "Cédula, correo o clave incorrectos.", 401)
    _abrir_sesion(fila)
    return g.usuario


def entrar_como_demo(rol):
    """Solo en modo demo y solo con usuarios marcados `es_demo`: nunca abre la sesión de un usuario real."""
    if not current_app.config.get("MODO_DEMO") or rol not in ROLES:
        raise ErrorDeDominio("no_encontrado", "No existe.", 404)
    with transaccion() as cursor:
        fila = repositorio.primer_usuario_demo(cursor, rol)
    if fila is None:
        raise ErrorDeDominio("sin_usuario_demo", "La demo no tiene un usuario para ese rol.", 404)
    _abrir_sesion(fila)
    return g.usuario


def cerrar_sesion():
    session.clear()
    g.pop("usuario", None)


def usuario_actual():
    """El usuario de la sesión, releído de la base en cada solicitud: un rol cambiado o un usuario inactivo pesan ya."""
    if "usuario" in g:
        return g.usuario
    usuario = None
    texto = session.get("usuario_id")
    if texto:
        with transaccion() as cursor:
            fila = repositorio.buscar_por_id(cursor, desde_texto(texto))
        if fila and fila["activo"]:
            usuario = _publico(fila)
        else:
            session.clear()
    g.usuario = usuario
    return usuario


def requiere(permiso):
    """Decorador de rutas: 401 sin sesión, 403 si el rol no tiene el permiso de la matriz."""
    puede(ROLES[0], permiso)  # falla al importar si el permiso no existe

    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*argumentos, **nombrados):
            usuario = usuario_actual()
            if usuario is None:
                raise ErrorDeDominio("sin_sesion", "Tenés que iniciar sesión.", 401)
            if not puede(usuario["rol"], permiso):
                raise ErrorDeDominio("sin_permiso", "Tu rol no permite esta acción.", 403)
            return funcion(*argumentos, **nombrados)

        return envoltura

    return decorador


def crear_usuario(cursor, persona, rol, clave=None, es_demo=False, *, identificadores=None):
    """Crea persona y usuario dentro de la transacción del llamador. Sin clave, solo entra por "entrar como…"."""
    if rol not in ROLES:
        raise ValueError(f"rol desconocido: {rol!r}")
    if clave is not None and len(clave) < LARGO_MINIMO_DE_CLAVE:
        raise ErrorDeDominio("clave_corta", f"La clave necesita al menos {LARGO_MINIMO_DE_CLAVE} caracteres.", 422)
    reloj = reloj_actual()
    ahora = reloj.ahora()
    datos = dict(persona, cedula=normalizar_cedula(persona["cedula"]))
    if datos.get("correo"):
        datos["correo"] = datos["correo"].strip().lower()
    # La semilla puede aportar identidades ficticias estables; el repositorio valida UUIDv7.
    persona_id, usuario_id = identificadores if identificadores is not None else (nuevo_id(reloj), nuevo_id(reloj))
    repositorio.insertar_persona(cursor, persona_id, datos, ahora)
    clave_hash = generate_password_hash(clave) if clave else None
    repositorio.insertar_usuario(cursor, usuario_id, persona_id, rol, clave_hash, es_demo, ahora)
    return usuario_id


def registrar_consentimiento(cursor, socio_id, tipo, otorgado, version_texto, autor_id, *, identificador=None):
    """Otorgar y revocar agregan un registro; nunca se modifica uno anterior (ADR 0003)."""
    if tipo not in TIPOS_DE_CONSENTIMIENTO:
        raise ValueError(f"tipo de consentimiento desconocido: {tipo!r}")
    reloj = reloj_actual()
    repositorio.insertar_consentimiento(
        cursor,
        identificador if identificador is not None else nuevo_id(reloj),
        socio_id,
        tipo,
        version_texto,
        otorgado,
        autor_id,
        reloj.ahora(),
    )


def tiene_consentimiento(cursor, socio_id, tipo):
    vigente = repositorio.consentimiento_vigente(cursor, socio_id, tipo)
    return bool(vigente and vigente["otorgado"])


def tiene_asignacion_vigente(cursor, socio_id, entrenador_id):
    """Consulta el alcance del entrenador dentro de la transacción del servicio de dominio.

    Vigente significa `hasta IS NULL`, con ambos usuarios activos y sus roles correspondientes.
    No reemplaza `@requiere`: el servicio de entrenamiento valida usuario propio o socio asignado.
    """
    return repositorio.tiene_asignacion_vigente(cursor, socio_id, entrenador_id)
