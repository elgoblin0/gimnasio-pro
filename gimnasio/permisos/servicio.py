"""Acceso por rol, "entrar como…" en modo demo y consentimientos (ADR 0006). Ruta sensible."""

import secrets
from contextlib import contextmanager
from datetime import UTC, datetime, time, timedelta
from functools import cache, wraps

from flask import current_app, g, session
from mysql.connector import Error as ErrorMySQL
from mysql.connector import IntegrityError
from mysql.connector.errorcode import ER_LOCK_DEADLOCK as INTERBLOQUEO_MYSQL
from werkzeug.security import check_password_hash, generate_password_hash

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.formatos import normalizar_cedula
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import ZONA_SEDE, fecha_local, reloj_actual
from gimnasio.permisos import repositorio
from gimnasio.permisos.matriz import ROLES, puede

VENTANA_DE_INTENTOS = timedelta(minutes=15)
MAX_FALLIDOS_POR_USUARIO = 5
SEGUNDOS_DE_ESPERA_DEL_CANDADO = 10
MAX_FALLIDOS_POR_IP = 20
LARGO_MINIMO_DE_CLAVE = 8
TIPOS_DE_CONSENTIMIENTO = ("datos_personales", "salud", "imagen")
FIGURAS_CUERPO = ("masculina", "femenina")


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
        "figura_cuerpo": fila["figura_cuerpo"],
        "debe_cambiar_clave": bool(fila.get("debe_cambiar_clave", False)),
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


def entrar_como_demo(rol, usuario_id=None):
    """Solo en modo demo y solo con usuarios marcados `es_demo`: nunca abre la sesión de un usuario real."""
    if not current_app.config.get("MODO_DEMO") or rol not in ROLES:
        raise ErrorDeDominio("no_encontrado", "No existe.", 404)
    with transaccion() as cursor:
        if usuario_id is None:
            fila = repositorio.primer_usuario_demo(cursor, rol)
        else:
            try:
                fila = repositorio.buscar_por_id(cursor, desde_texto(usuario_id))
            except (ValueError, TypeError, AttributeError):
                fila = None
            if fila and (not fila["es_demo"] or not fila["activo"] or fila["rol"] != rol):
                fila = None
    if fila is None:
        raise ErrorDeDominio("sin_usuario_demo", "La demo no tiene un usuario para ese rol.", 404)
    _abrir_sesion(fila)
    return g.usuario


def socios_demo():
    if not current_app.config.get("MODO_DEMO"):
        raise ErrorDeDominio("no_encontrado", "No existe.", 404)
    with transaccion() as cursor:
        return [{**fila, "id": str(desde_bytes(fila["id"]))} for fila in repositorio.listar_socios_demo(cursor)]


def contar_altas_demo(cursor, desde, hasta):
    return repositorio.contar_altas_demo(cursor, desde, hasta)


def comprobar_tope_demo(cursor):
    ahora = reloj_actual().ahora()
    desde = datetime.combine(fecha_local(ahora), time.min, ZONA_SEDE).astimezone(UTC)
    if contar_altas_demo(cursor, desde, desde + timedelta(days=1)) >= 20:
        raise ErrorDeDominio("limite_altas_demo", "La demo admite 20 altas por día.", 429)


def _id_usuario(texto):
    try:
        return desde_texto(texto)
    except (ValueError, TypeError, AttributeError) as error:
        raise ErrorDeDominio("usuario_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def alta_personal(datos, es_demo):
    from gimnasio.socios.servicio import validar_datos_personales

    campos = {"nombre", "apellido", "cedula", "telefono", "correo", "fecha_nacimiento"}
    if (
        not isinstance(datos, dict)
        or set(datos) - (campos | {"rol"})
        or not {"nombre", "apellido", "cedula", "rol"} <= datos.keys()
        or datos["rol"] not in ("recepcion", "entrenador", "administracion")
    ):
        raise ErrorDeDominio("datos_invalidos", "Enviá los datos personales y un rol del personal.", 422)
    persona = validar_datos_personales({campo: valor for campo, valor in datos.items() if campo in campos})
    clave = None if es_demo else secrets.token_urlsafe(18)
    try:
        with transaccion() as cursor:
            if es_demo:
                comprobar_tope_demo(cursor)
            identificador = crear_usuario(cursor, persona, datos["rol"], es_demo=es_demo)
            if clave:
                fijar_clave_provisional(cursor, identificador, clave)
            return {"usuario_id": str(identificador), "clave_ya_entregada": False} | (
                {"clave_provisional": clave} if clave else {}
            )
    except IntegrityError as error:
        if error.errno == 1062:
            raise ErrorDeDominio("datos_repetidos", "La cédula o el correo ya están registrados.", 409) from error
        raise


def restablecer_clave(texto, es_demo):
    identificador = _id_usuario(texto)
    with transaccion() as cursor:
        fila = repositorio.buscar_por_id(cursor, identificador, bloquear=True)
        if fila is None:
            raise ErrorDeDominio("usuario_no_encontrado", "No se encontró el usuario.", 404)
        if es_demo or fila["es_demo"]:
            raise ErrorDeDominio("sin_claves_demo", "La demo no permite restablecer claves.", 409)
        clave = secrets.token_urlsafe(18)
        fijar_clave_provisional(cursor, identificador, clave)
        return {"usuario_id": texto, "clave_provisional": clave, "clave_ya_entregada": False}


def _lista_publica(filas):
    return [{**fila, "id": str(desde_bytes(fila["id"]))} for fila in filas]


def consultar_usuarios(filtros):
    rol, activo, consulta = filtros.get("rol") or None, filtros.get("activo") or None, filtros.get("q", "")
    try:
        pagina = int(filtros.get("pagina", "1"))
        if (
            pagina < 1
            or pagina > 1000000
            or rol not in (None, *ROLES)
            or activo not in (None, "true", "false", "1", "0")
            or len(consulta) > 160
        ):
            raise ValueError
    except (ValueError, TypeError) as error:
        raise ErrorDeDominio("filtros_invalidos", "Revisá rol, activo y página.", 422) from error
    with transaccion() as cursor:
        filas = repositorio.listar_usuarios(
            cursor, rol, consulta, None if activo is None else activo in ("true", "1"), pagina
        )
    return {"usuarios": _lista_publica(filas[:50]), "pagina": pagina, "hay_mas": len(filas) > 50}


def consultar_sin_entrenador():
    with transaccion() as cursor:
        return {"socios": _lista_publica(repositorio.socios_sin_entrenador(cursor))}


def asignar_entrenador(texto, datos):
    if not isinstance(datos, dict) or set(datos) != {"entrenador_id"}:
        raise ErrorDeDominio("datos_invalidos", "Enviá entrenador_id.", 422)
    socio_id, entrenador_id = _id_usuario(texto), _id_usuario(datos["entrenador_id"])
    with transaccion() as cursor:
        # El mismo usuario serializa la publicación de programas y los cambios de asignación.
        socio = repositorio.buscar_por_id(cursor, socio_id, bloquear=True)
        if socio is None or socio["rol"] != "socio" or not socio["activo"]:
            raise ErrorDeDominio("socio_no_encontrado", "No se encontró el socio activo.", 404)
        entrenador = repositorio.buscar_por_id(cursor, entrenador_id, bloquear=True)
        if entrenador is None or entrenador["rol"] != "entrenador" or not entrenador["activo"]:
            raise ErrorDeDominio("entrenador_invalido", "Elegí un entrenador activo.", 422)
        if not repositorio.cambiar_asignacion(cursor, nuevo_id(), socio_id, entrenador_id, reloj_actual().ahora()):
            raise ErrorDeDominio("asignacion_sin_cambio", "El socio ya tiene ese entrenador.", 409)
    return {"socio_id": texto, "entrenador_id": datos["entrenador_id"]}


def fijar_clave_provisional(cursor, usuario_id, clave):
    repositorio.cambiar_clave(cursor, usuario_id, generate_password_hash(clave), True, reloj_actual().ahora())


def cambiar_clave(datos):
    usuario = usuario_actual()
    if usuario is None:
        raise ErrorDeDominio("sin_sesion", "Tenés que iniciar sesión.", 401)
    if not isinstance(datos, dict) or not isinstance(datos.get("clave_actual"), str):
        raise ErrorDeDominio("datos_invalidos", "Enviá la clave actual y la nueva.", 422)
    nueva = datos.get("clave_nueva")
    if not isinstance(nueva, str) or len(nueva) < 10:
        raise ErrorDeDominio("clave_corta", "La clave necesita al menos 10 caracteres.", 422)
    with transaccion() as cursor:
        fila = repositorio.buscar_por_id(cursor, desde_texto(usuario["id"]), bloquear=True)
        if not fila["clave_hash"] or not check_password_hash(fila["clave_hash"], datos["clave_actual"]):
            raise ErrorDeDominio("credenciales_invalidas", "La clave actual es incorrecta.", 403)
        if check_password_hash(fila["clave_hash"], nueva):
            raise ErrorDeDominio("clave_repetida", "La clave nueva tiene que ser distinta de la actual.", 422)
        repositorio.cambiar_clave(
            cursor, desde_texto(usuario["id"]), generate_password_hash(nueva), False, reloj_actual().ahora()
        )
    g.usuario = {**usuario, "debe_cambiar_clave": False}
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


def cambiar_figura_cuerpo(figura):
    """Cada usuario elige la suya; solo cambia cómo se ve su cuerpo 3D (ADR 0020)."""
    usuario = usuario_actual()
    if usuario is None:
        raise ErrorDeDominio("sin_sesion", "Tenés que iniciar sesión.", 401)
    if figura not in FIGURAS_CUERPO:
        raise ErrorDeDominio("figura_invalida", "Elegí una figura masculina o femenina.", 422)
    with transaccion() as cursor:
        repositorio.actualizar_figura_cuerpo(cursor, desde_texto(usuario["id"]), figura, reloj_actual().ahora())
    g.usuario = {**usuario, "figura_cuerpo": figura}
    return g.usuario


def requiere(permiso, *alternativos):
    """Exige sesión y al menos uno de los permisos indicados en la matriz."""
    puede(ROLES[0], permiso)  # falla al importar si el permiso no existe
    for alternativo in alternativos:
        puede(ROLES[0], alternativo)

    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*argumentos, **nombrados):
            usuario = usuario_actual()
            if usuario is None:
                raise ErrorDeDominio("sin_sesion", "Tenés que iniciar sesión.", 401)
            if not any(puede(usuario["rol"], opcion) for opcion in (permiso, *alternativos)):
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
    if datos.get("figura_cuerpo"):
        repositorio.actualizar_figura_cuerpo(cursor, usuario_id, datos["figura_cuerpo"], ahora)
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


def socios_asignados(cursor, entrenador_id):
    """Lectura de asignaciones vigentes para servicios que ya exigen el permiso."""
    return [
        {**fila, "id": str(desde_bytes(fila["id"]))}
        for fila in repositorio.listar_socios_asignados(cursor, entrenador_id)
    ]


def cambiar_estado_usuario(texto, datos, activo, autor):
    for intento in range(3):
        try:
            return _cambiar_estado_usuario(texto, datos, activo, autor)
        except ErrorMySQL as error:
            if error.errno != INTERBLOQUEO_MYSQL or intento == 2:
                raise


def _cambiar_estado_usuario(texto, datos, activo, autor):
    from gimnasio.clases.servicio import cancelar_reservas_por_baja, exigir_sin_clases_a_cargo
    from gimnasio.visitas.servicio import exigir_sin_visita_abierta

    if datos is None:
        datos = {}
    if (
        not isinstance(datos, dict)
        or set(datos) - ({"por_revocacion"} if not activo else set())
        or type(datos.get("por_revocacion", False)) is not bool
    ):
        raise ErrorDeDominio("datos_invalidos", "Enviá por_revocacion como verdadero o falso al desactivar.", 422)
    usuario_id = _id_usuario(texto)
    ahora = reloj_actual().ahora()
    momento = ahora.astimezone(UTC).replace(tzinfo=None)
    with transaccion() as cursor:
        # Serializa bajas simultáneas de administración antes de bloquear la cuenta elegida.
        administraciones = repositorio.bloquear_administraciones(cursor)
        fila = repositorio.buscar_por_id(cursor, usuario_id, bloquear=True)
        if fila is None:
            raise ErrorDeDominio("usuario_no_encontrado", "No se encontró el usuario.", 404)
        if current_app.config["MODO_DEMO"] and fila["es_demo"]:
            raise ErrorDeDominio("usuario_demo_protegido", "Este usuario permite entrar como… en la demo.", 409)
        if datos.get("por_revocacion") and fila["rol"] != "socio":
            raise ErrorDeDominio("datos_invalidos", "La revocación de datos personales corresponde a un socio.", 422)
        if bool(fila["activo"]) == activo:
            return {"usuario_id": texto, "activo": activo}
        if not activo:
            if fila["rol"] == "socio":
                exigir_sin_visita_abierta(cursor, usuario_id)
                cancelar_reservas_por_baja(cursor, usuario_id, desde_texto(autor["id"]), ahora)
                if datos.get("por_revocacion"):
                    vigente = repositorio.consentimiento_vigente(cursor, usuario_id, "datos_personales")
                    registrar_consentimiento(
                        cursor,
                        usuario_id,
                        "datos_personales",
                        False,
                        vigente["version_texto"] if vigente else "1",
                        desde_texto(autor["id"]),
                    )
            elif fila["rol"] == "entrenador":
                exigir_sin_clases_a_cargo(cursor, usuario_id, ahora)
            elif fila["rol"] == "administracion" and len(administraciones) == 1:
                raise ErrorDeDominio("ultima_administracion", "Debe quedar una cuenta activa de administración.", 409)
            repositorio.cerrar_asignaciones(cursor, usuario_id, momento)
        repositorio.cambiar_activo(cursor, usuario_id, activo, momento)
    return {"usuario_id": texto, "activo": activo}
