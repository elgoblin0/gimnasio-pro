"""Configuración de clases y agenda de dos semanas en la zona de la sede."""

import re
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from mysql.connector import Error as ErrorMySQL
from mysql.connector.errorcode import ER_LOCK_DEADLOCK as INTERBLOQUEO_MYSQL

from gimnasio.clases import repositorio
from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.reglas.clases import cambios_de_estado, estado_reservas, ocurrencias_en_rango
from gimnasio.socios import servicio as socios


def identificador(texto):
    try:
        return desde_texto(texto)
    except (ValueError, TypeError, AttributeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def validar(datos):
    if not isinstance(datos, dict):
        raise ErrorDeDominio("clase_invalida", "Enviá los datos de la clase.", 422)
    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 120:
        raise ErrorDeDominio("nombre_invalido", "El nombre admite entre 1 y 120 caracteres.", 422)
    for campo, minimo, maximo in (("dia_semana", 1, 7), ("duracion_minutos", 15, 240), ("cupo", 1, 2147483647)):
        valor = datos.get(campo)
        if type(valor) is not int or not minimo <= valor <= maximo:
            raise ErrorDeDominio("clase_invalida", f"{campo}: enviá un entero entre {minimo} y {maximo}.", 422)
    hora = datos.get("hora_inicio")
    if not isinstance(hora, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", hora):
        raise ErrorDeDominio("hora_invalida", "La hora debe usar HH:MM.", 422)
    return {campo: datos[campo] for campo in ("dia_semana", "duracion_minutos", "cupo", "hora_inicio")} | {
        "nombre": nombre.strip(),
        "entrenador_id": identificador(datos.get("entrenador_id")),
    }


def _hora(valor):
    # MySQL entrega TIME como timedelta; la API usa HH:MM.
    segundos = int(valor.total_seconds())
    return f"{segundos // 3600:02d}:{segundos % 3600 // 60:02d}"


def _clases(cursor):
    return [
        dict(
            fila,
            id=str(desde_bytes(fila["id"])),
            entrenador_id=str(desde_bytes(fila["entrenador_id"])),
            hora_inicio=_hora(fila["hora_inicio"]),
            archivada=bool(fila["archivada"]),
            creada_en=fila["creada_en"].replace(tzinfo=UTC).isoformat(),
            actualizada_en=fila["actualizada_en"].replace(tzinfo=UTC).isoformat(),
        )
        for fila in repositorio.listar(cursor)
    ]


def listar():
    with transaccion() as cursor:
        return {
            "clases": _clases(cursor),
            "entrenadores": [dict(fila, id=str(desde_bytes(fila["id"]))) for fila in repositorio.entrenadores(cursor)],
        }


def agenda(usuario=None, socio_texto=None):
    socio_id = _socio_consulta(usuario, socio_texto)
    with transaccion() as cursor:
        zona_horaria = repositorio.zona_horaria(cursor)
        hoy = reloj_actual().ahora().astimezone(ZoneInfo(zona_horaria)).date()
        desde = hoy - timedelta(days=hoy.weekday())
        hasta = desde + timedelta(days=13)
        clases = _clases(cursor)
        ocurrencias = [
            dict(fila, clase_id=str(desde_bytes(fila["clase_id"])), hora_inicio=_hora(fila["hora_inicio"]))
            for fila in repositorio.ocurrencias(cursor, desde, hasta)
        ]
        reservas = defaultdict(list)
        for reserva in repositorio.reservas_en_rango(cursor, desde, hasta):
            reservas[(str(desde_bytes(reserva["clase_id"])), reserva["fecha"])].append(reserva)
    por_id = {clase["id"]: clase for clase in clases}
    fijadas = {(fila["clase_id"], fila["fecha"]): fila for fila in ocurrencias}
    resultado = []
    for fila in ocurrencias_en_rango(clases, ocurrencias, desde, hasta):
        clase = por_id[fila["clase_id"]]
        if usuario and usuario["rol"] == "entrenador" and clase["entrenador_id"] != usuario["id"]:
            continue
        activas = reservas[(clase["id"], fila["fecha"])]
        fijada = fijadas.get((clase["id"], fila["fecha"]), {})
        cupo = fijada.get("cupo", clase["cupo"])
        cancelada = bool(fijada.get("cancelada", False))
        estado = estado_reservas(cupo, activas)
        propia = next((r for r in activas if socio_id and r["socio_id"] == socio_id.bytes), None)
        fecha = fila["fecha"].isoformat()
        resultado.append(
            dict(
                fila,
                fecha=fecha,
                identificador={"clase_id": clase["id"], "fecha": fecha},
                clase=clase["nombre"],
                entrenador_id=clase["entrenador_id"],
                entrenador=f"{clase['entrenador_nombre']} {clase['entrenador_apellido']}",
                cupo=cupo,
                cancelada=cancelada,
                libres=0 if cancelada else cupo - len(estado["con_lugar"]),
                espera=len(estado["en_espera"]),
                reserva=_estado_propio(estado, propia),
            )
        )
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "zona_horaria": zona_horaria,
        "ocurrencias": resultado,
    }


def _socio_consulta(usuario, texto):
    if usuario and usuario["rol"] == "socio":
        if texto is not None and texto != usuario["id"]:
            raise ErrorDeDominio("sin_permiso", "Solo podés reservar para vos.", 403)
        return identificador(usuario["id"])
    if texto is not None:
        if not usuario or usuario["rol"] != "recepcion":
            raise ErrorDeDominio("sin_permiso", "Tu rol no permite gestionar reservas.", 403)
        return identificador(texto)
    return None


def _estado_propio(estado, reserva):
    if reserva is None:
        return None
    posicion = next((r["posicion"] for r in estado["en_espera"] if r["id"] == reserva["id"]), None)
    return {
        "id": str(desde_bytes(reserva["id"])),
        "estado": "en_espera" if posicion else "con_lugar",
        "posicion": posicion,
    }


def _fecha(texto):
    try:
        if not isinstance(texto, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
            raise ValueError
        return date.fromisoformat(texto)
    except ValueError as error:
        raise ErrorDeDominio("fecha_invalida", "Enviá la fecha como AAAA-MM-DD.", 422) from error


def _inicio(ocurrencia):
    return datetime.combine(ocurrencia["fecha"], time()) + ocurrencia["hora_inicio"]


def _exigir_sin_empezar(cursor, ocurrencia):
    zona = ZoneInfo(repositorio.zona_horaria(cursor))
    ahora = reloj_actual().ahora().astimezone(zona).replace(tzinfo=None)
    if _inicio(ocurrencia) <= ahora:
        raise ErrorDeDominio("ocurrencia_empezada", "La ocurrencia de clase ya empezó.", 409)
    return ahora.date()


def reservar(datos, usuario):
    if not isinstance(datos, dict) or set(datos) - {"clase_id", "fecha", "socio_id"}:
        raise ErrorDeDominio("reserva_invalida", "Enviá clase_id, fecha y, en recepción, socio_id.", 422)
    socio_id = _socio_consulta(usuario, datos.get("socio_id"))
    if socio_id is None:
        raise ErrorDeDominio("socio_invalido", "Elegí un socio para reservar.", 422)
    clase_id, fecha = identificador(datos.get("clase_id")), _fecha(datos.get("fecha"))
    with transaccion() as cursor:
        # El socio serializa también solicitudes a clases distintas que se superponen.
        socios.bloquear_socio_activo(socio_id, cursor=cursor)
        clase = repositorio.clase_para_reserva(cursor, clase_id)
        if clase is None:
            raise ErrorDeDominio("clase_inexistente", "La clase no existe.", 404)
        ocurrencia = repositorio.ocurrencia_para_reserva(cursor, clase_id, fecha)
        candidata = ocurrencia or dict(clase, fecha=fecha)
        if ocurrencia and ocurrencia["cancelada"]:
            raise ErrorDeDominio("ocurrencia_cancelada", "La ocurrencia de clase está cancelada.", 409)
        hoy = _exigir_sin_empezar(cursor, candidata)
        desde = hoy - timedelta(days=hoy.weekday())
        if not desde <= fecha <= desde + timedelta(days=13) or (
            ocurrencia is None and (clase["archivada"] or fecha.isoweekday() != clase["dia_semana"])
        ):
            raise ErrorDeDominio("fuera_de_agenda", "Elegí una ocurrencia de la agenda.", 422)
        activas = repositorio.reservas_del_socio(cursor, socio_id)
        for reserva in activas:
            if ocurrencia and reserva["ocurrencia_id"] == ocurrencia["id"]:
                raise ErrorDeDominio("ya_reservada", "Ya tenés una reserva activa en esa ocurrencia.", 409)
            if _inicio(reserva) < _inicio(candidata) + timedelta(minutes=candidata["duracion_minutos"]) and (
                _inicio(candidata) < _inicio(reserva) + timedelta(minutes=reserva["duracion_minutos"])
            ):
                raise ErrorDeDominio("reserva_superpuesta", "Ya tenés una reserva en ese horario.", 409)
        if socios.consultar_membresia(socio_id, fecha, cursor=cursor) is None:
            raise ErrorDeDominio("membresia_no_vigente", "La membresía no está vigente en la fecha de la clase.", 422)
        ahora = reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
        if ocurrencia is None:
            repositorio.fijar_ocurrencia(cursor, nuevo_id(), clase, fecha, ahora)
            ocurrencia = repositorio.ocurrencia_para_reserva(cursor, clase_id, fecha)
        reserva_id = nuevo_id()
        repositorio.insertar_reserva(
            cursor, reserva_id, ocurrencia["id"], socio_id, ahora, identificador(usuario["id"])
        )
        activas = repositorio.reservas_ocurrencia(cursor, ocurrencia["id"])
        return _estado_propio(estado_reservas(ocurrencia["cupo"], activas), {"id": reserva_id.bytes})


def cancelar(texto_id, usuario):
    for intento in range(3):
        try:
            return _cancelar_en_transaccion(texto_id, usuario)
        except ErrorMySQL as error:
            if error.errno != INTERBLOQUEO_MYSQL or intento == 2:
                raise
            # transaccion() ya revirtió todo: se releen reservas y se recalculan avisos.


def _cancelar_en_transaccion(texto_id, usuario):
    reserva_id = identificador(texto_id)
    with transaccion() as cursor:
        reserva = repositorio.obtener_reserva(cursor, reserva_id)
        if reserva is None:
            raise ErrorDeDominio("reserva_inexistente", "La reserva no existe.", 404)
        if usuario["rol"] == "socio" and reserva["socio_id"] != identificador(usuario["id"]).bytes:
            raise ErrorDeDominio("sin_permiso", "Solo podés cancelar tus reservas.", 403)
        socios.bloquear_socio_activo(desde_bytes(reserva["socio_id"]), cursor=cursor)
        repositorio.clase_para_reserva(cursor, desde_bytes(reserva["clase_id"]))
        ocurrencia = repositorio.ocurrencia_para_reserva(cursor, desde_bytes(reserva["clase_id"]), reserva["fecha"])
        _exigir_sin_empezar(cursor, ocurrencia)
        if repositorio.cancelacion(cursor, reserva_id) is None:
            activas = repositorio.reservas_ocurrencia(cursor, ocurrencia["id"])
            antes = estado_reservas(ocurrencia["cupo"], activas)
            ahora = reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
            repositorio.cancelar_reserva(
                cursor,
                nuevo_id(),
                reserva_id,
                identificador(usuario["id"]),
                ahora,
            )
            despues = estado_reservas(ocurrencia["cupo"], [r for r in activas if r["id"] != reserva_id.bytes])
            _avisar_cambios(cursor, ocurrencia, activas, antes, despues, ahora)
        return {"id": texto_id}


def listar_reservas(texto_id, texto_fecha, usuario):
    clase_id, fecha = identificador(texto_id), _fecha(texto_fecha)
    with transaccion() as cursor:
        clase = repositorio.clase_para_reserva(cursor, clase_id)
        if clase is None:
            raise ErrorDeDominio("clase_inexistente", "La clase no existe.", 404)
        if usuario["rol"] == "entrenador" and clase["entrenador_id"] != identificador(usuario["id"]).bytes:
            raise ErrorDeDominio("sin_permiso", "Solo podés ver las reservas de tus clases.", 403)
        reservas = repositorio.lista_reservas(cursor, clase_id, fecha)
        estado = estado_reservas(reservas[0]["cupo"] if reservas else clase["cupo"], reservas)
        return {
            "reservas": [
                {"nombre": r["nombre"], **{k: v for k, v in _estado_propio(estado, r).items() if k != "id"}}
                for r in reservas
            ]
        }


def guardar(datos, texto_id=None):
    datos = validar(datos)
    nueva = texto_id is None
    clase_id = nuevo_id() if nueva else identificador(texto_id)
    momento = reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
    with transaccion() as cursor:
        anterior = repositorio.bloquear(cursor, clase_id) if not nueva else None
        if not nueva and anterior is None:
            raise ErrorDeDominio("clase_inexistente", "La clase no existe.", 404)
        if not repositorio.entrenador_activo(cursor, datos["entrenador_id"]):
            raise ErrorDeDominio("entrenador_invalido", "Elegí un usuario activo con rol entrenador.", 422)
        if anterior and anterior["cupo"] != datos["cupo"]:
            ahora_local = (
                reloj_actual().ahora().astimezone(ZoneInfo(repositorio.zona_horaria(cursor))).replace(tzinfo=None)
            )
            for ocurrencia in repositorio.ocurrencias_de_clase(cursor, clase_id):
                if _inicio(ocurrencia) <= ahora_local:
                    if ocurrencia["cupo_id"] is None:
                        repositorio.fijar_cupo(cursor, nuevo_id(), ocurrencia["id"], anterior["cupo"], momento)
                elif not ocurrencia["cancelada"]:
                    activas = repositorio.reservas_ocurrencia(cursor, ocurrencia["id"])
                    antes = estado_reservas(ocurrencia["cupo"], activas)
                    despues = estado_reservas(datos["cupo"], activas)
                    _avisar_cambios(cursor, ocurrencia, activas, antes, despues, momento)
        repositorio.guardar(cursor, clase_id, datos, momento, nueva=nueva)
    return {"id": str(clase_id)}


def archivar(texto_id):
    clase_id = identificador(texto_id)
    momento = reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
    with transaccion() as cursor:
        if repositorio.bloquear(cursor, clase_id) is None:
            raise ErrorDeDominio("clase_inexistente", "La clase no existe.", 404)
        repositorio.archivar(cursor, clase_id, momento)
    return {"id": str(clase_id), "archivada": True}


def _avisar_cambios(cursor, ocurrencia, reservas, antes, despues, ahora):
    cambios = cambios_de_estado(antes, despues)
    por_id = {reserva["id"]: reserva["socio_id"] for reserva in reservas}
    for campo, tipo in (("pasaron_a_tener_lugar", "paso_a_tener_lugar"), ("volvieron_a_espera", "volvio_a_espera")):
        for reserva_id in cambios[campo]:
            repositorio.insertar_aviso(cursor, nuevo_id(), por_id[reserva_id], ocurrencia["id"], tipo, ahora)


def cancelar_ocurrencia(texto_id, texto_fecha, datos, usuario):
    motivo = datos.get("motivo") if isinstance(datos, dict) else None
    if not isinstance(motivo, str) or not motivo.strip():
        raise ErrorDeDominio("motivo_obligatorio", "Escribí el motivo de la cancelación.", 422)
    clase_id, fecha = identificador(texto_id), _fecha(texto_fecha)
    ahora = reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
    autor = identificador(usuario["id"])
    with transaccion() as cursor:
        clase = repositorio.clase_para_reserva(cursor, clase_id)
        if clase is None:
            raise ErrorDeDominio("clase_inexistente", "La clase no existe.", 404)
        ocurrencia = repositorio.ocurrencia_para_reserva(cursor, clase_id, fecha)
        if ocurrencia is None:
            if clase["archivada"] or fecha.isoweekday() != clase["dia_semana"]:
                raise ErrorDeDominio("fuera_de_agenda", "Elegí una ocurrencia de la agenda.", 422)
            repositorio.fijar_ocurrencia(cursor, nuevo_id(), clase, fecha, ahora)
            ocurrencia = repositorio.ocurrencia_para_reserva(cursor, clase_id, fecha)
        if not ocurrencia["cancelada"]:
            activas = repositorio.reservas_ocurrencia(cursor, ocurrencia["id"])
            repositorio.cancelar_ocurrencia(cursor, nuevo_id(), ocurrencia["id"], motivo.strip(), autor, ahora)
            for reserva in activas:
                repositorio.cancelar_reserva(cursor, nuevo_id(), desde_bytes(reserva["id"]), autor, ahora)
                repositorio.insertar_aviso(
                    cursor, nuevo_id(), reserva["socio_id"], ocurrencia["id"], "ocurrencia_cancelada", ahora
                )
    return {"clase_id": texto_id, "fecha": texto_fecha, "cancelada": True}


def avisos_propios(usuario):
    with transaccion() as cursor:
        return {
            "avisos": [
                {
                    "id": str(desde_bytes(fila["id"])),
                    "ocurrencia_id": str(desde_bytes(fila["ocurrencia_id"])),
                    "tipo": fila["tipo"],
                    "clase": fila["clase"],
                    "fecha": fila["fecha"].isoformat(),
                    "hora_inicio": _hora(fila["hora_inicio"]),
                    "cupo": fila["cupo"],
                    "registrado_en": fila["registrado_en"].replace(tzinfo=UTC).isoformat(),
                }
                for fila in repositorio.avisos_sin_ver(cursor, identificador(usuario["id"]))
            ]
        }


def ver_aviso(texto_id, usuario):
    aviso_id = identificador(texto_id)
    with transaccion() as cursor:
        if repositorio.aviso_propio(cursor, aviso_id, identificador(usuario["id"])) is None:
            raise ErrorDeDominio("aviso_inexistente", "El aviso al socio no existe.", 404)
        repositorio.marcar_aviso(
            cursor, nuevo_id(), aviso_id, reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
        )
    return {"id": texto_id}
