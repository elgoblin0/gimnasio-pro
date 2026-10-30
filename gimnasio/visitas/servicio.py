"""Entrada atómica: sede, socio, vigencia, visita abierta y aforo, en ese orden."""

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.formatos import formatear_cedula
from gimnasio.comun.ids import desde_bytes, desde_texto
from gimnasio.comun.reloj import fecha_local, reloj_actual
from gimnasio.reglas.horarios import calcular_mejores_horarios
from gimnasio.reglas.permanencia import calcular_permanencia_habitual, es_visita_por_conciliar
from gimnasio.socios.servicio import consultar_membresia, membresia_para_tarjeta
from gimnasio.visitas import repositorio


def identificar(texto):
    try:
        if not isinstance(texto, str):
            raise ValueError("El identificador debe ser texto.")
        return desde_texto(texto)
    except (ValueError, AttributeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def consultar_tarjeta(socio_id):
    socio_id = identificar(socio_id)
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        socio = repositorio.buscar_socio_para_tarjeta(cursor, socio_id)
        if socio is None:
            raise ErrorDeDominio("socio_inexistente", "El socio no existe.", 404)
        sede = repositorio.obtener_sede(cursor)
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        visitas = repositorio.listar_visitas_del_socio(cursor, socio_id, ahora)
        duraciones = repositorio.listar_duraciones_confiables(
            cursor, desde_bytes(sede["id"]), ahora - timedelta(weeks=8), ahora, socio_id
        )
    abierta = next((visita for visita in visitas if visita["abierta"]), None)
    ultima = next((visita for visita in visitas if visita["salida_registrada_en"] is not None), None)
    return {
        "socio": {
            "id": str(socio_id),
            "nombre": socio["nombre"],
            "apellido": socio["apellido"],
            "cedula": formatear_cedula(socio["cedula"]),
        },
        "membresia": membresia_para_tarjeta(socio_id, fecha_local(ahora, ZoneInfo(sede["zona_horaria"]))),
        "visita_abierta": {
            "entrada_id": str(desde_bytes(abierta["entrada_id"])),
            "desde": abierta["registrada_en"].replace(tzinfo=UTC).isoformat(),
            "minutos": max(0, int((ahora - abierta["registrada_en"].replace(tzinfo=UTC)).total_seconds()) // 60),
        }
        if abierta
        else None,
        "ultima_visita": {
            "desde": ultima["registrada_en"].replace(tzinfo=UTC).isoformat(),
            "hasta": ultima["salida_registrada_en"].replace(tzinfo=UTC).isoformat(),
        }
        if ultima
        else None,
        "visitas_ultimas_4_semanas": sum(
            visita["registrada_en"].replace(tzinfo=UTC) >= ahora - timedelta(weeks=4) for visita in visitas
        ),
        "permanencia_habitual": asdict(calcular_permanencia_habitual(tuple(fila["minutos"] for fila in duraciones))),
    }


def validar_cuerpo(datos, campos):
    if not isinstance(datos, dict) or set(datos) != set(campos):
        raise ErrorDeDominio("cuerpo_invalido", "Enviá únicamente los campos requeridos.", 422)
    return {campo: identificar(datos[campo]) for campo in campos}


def entrada_publica(fila):
    return {
        "id": str(desde_bytes(fila["id"])),
        "socio_id": str(desde_bytes(fila["socio_id"])),
        "sede_id": str(desde_bytes(fila["sede_id"])),
        "autor_id": str(desde_bytes(fila["autor_id"])),
        "registrada_en": fila["registrada_en"].replace(tzinfo=UTC).isoformat(),
    }


def registrar_entrada(datos, usuario):
    ids = validar_cuerpo(datos, ("id", "socio_id", "sede_id"))
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        sede = repositorio.bloquear_sede(cursor, ids["sede_id"])
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        socio = repositorio.bloquear_socio(cursor, ids["socio_id"])
        if socio is None or socio["rol"] != "socio":
            raise ErrorDeDominio("socio_inexistente", "El socio no existe.", 404)
        anterior = repositorio.obtener_entrada(cursor, ids["id"])
        if anterior is not None:
            if anterior["socio_id"] != socio["id"] or anterior["sede_id"] != sede["id"]:
                raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra entrada.", 403)
            return entrada_publica(anterior)
        membresia = consultar_membresia(ids["socio_id"], fecha_local(ahora, ZoneInfo(sede["zona_horaria"])))
        if not socio["activo"] or membresia is None:
            raise ErrorDeDominio("membresia_no_vigente", "El socio no tiene una membresía vigente.", 422)
        if repositorio.tiene_visita_abierta(cursor, ids["socio_id"]):
            raise ErrorDeDominio("visita_abierta", "El socio ya tiene una visita abierta.", 409)
        if repositorio.contar_ocupacion_registrada(cursor, ids["sede_id"]) >= sede["aforo_maximo"]:
            raise ErrorDeDominio("aforo_alcanzado", "Se alcanzó el aforo máximo. No se registró la entrada.", 409)
        repositorio.insertar_entrada(
            cursor, ids["id"], ids["socio_id"], ids["sede_id"], identificar(usuario["id"]), ahora
        )
        return entrada_publica(repositorio.obtener_entrada(cursor, ids["id"]))


def salida_publica(fila):
    return {
        "id": str(desde_bytes(fila["id"])),
        "entrada_id": str(desde_bytes(fila["entrada_id"])),
        "autor_id": str(desde_bytes(fila["autor_id"])),
        "registrada_en": fila["registrada_en"].replace(tzinfo=UTC).isoformat(),
    }


def registrar_salida(datos, usuario):
    ids = validar_cuerpo(datos, ("id", "entrada_id"))
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        referencia = repositorio.obtener_entrada(cursor, ids["entrada_id"])
        if referencia is None:
            raise ErrorDeDominio("entrada_inexistente", "La entrada no existe.", 404)
        if referencia["corrige_a"] is not None:
            raise ErrorDeDominio("entrada_invalida", "Usá el identificador de la entrada original.", 422)
        repositorio.bloquear_sede(cursor, desde_bytes(referencia["sede_id"]))
        repositorio.bloquear_socio(cursor, desde_bytes(referencia["socio_id"]))
        anterior = repositorio.obtener_salida(cursor, ids["id"])
        if anterior is not None:
            if anterior["entrada_id"] != referencia["id"]:
                raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra salida.", 403)
            return salida_publica(anterior)
        estado = repositorio.obtener_estado_vigente(cursor, ids["entrada_id"])
        if not estado["abierta"]:
            raise ErrorDeDominio("visita_cerrada", "La visita ya está cerrada o anulada.", 409)
        repositorio.insertar_salida(cursor, ids["id"], ids["entrada_id"], identificar(usuario["id"]), ahora)
        return salida_publica(repositorio.obtener_salida(cursor, ids["id"]))


def conciliar_salida(entrada_id, datos, usuario):
    entrada_id = identificar(entrada_id)
    if not isinstance(datos, dict) or set(datos) != {"id", "salida_en", "motivo"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá id, salida_en y motivo.", 422)
    salida_id = identificar(datos["id"])
    motivo = datos["motivo"]
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo) > 500:
        raise ErrorDeDominio("motivo_invalido", "Indicá un motivo de hasta 500 caracteres.", 422)
    try:
        salida_en = datetime.fromisoformat(datos["salida_en"])
        if salida_en.utcoffset() is None:
            raise ValueError
        salida_en = salida_en.astimezone(UTC)
    except (TypeError, ValueError) as error:
        raise ErrorDeDominio("salida_invalida", "Indicá una hora de salida con zona horaria.", 422) from error
    with transaccion() as cursor:
        referencia = repositorio.obtener_entrada(cursor, entrada_id)
        if referencia is None:
            raise ErrorDeDominio("entrada_inexistente", "La entrada no existe.", 404)
        if referencia["corrige_a"] is not None:
            raise ErrorDeDominio("entrada_invalida", "Usá el identificador de la entrada original.", 422)
        repositorio.bloquear_sede(cursor, desde_bytes(referencia["sede_id"]))
        repositorio.bloquear_socio(cursor, desde_bytes(referencia["socio_id"]))
        anterior = repositorio.obtener_salida(cursor, salida_id)
        if anterior is not None:
            if anterior["entrada_id"] != referencia["id"]:
                raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra salida.", 403)
            return salida_publica(anterior)
        estado = repositorio.obtener_estado_vigente(cursor, entrada_id)
        if not estado["abierta"]:
            raise ErrorDeDominio("visita_cerrada", "La visita ya está cerrada o anulada.", 409)
        if not estado["registrada_en"].replace(tzinfo=UTC) < salida_en <= reloj_actual().ahora():
            raise ErrorDeDominio("salida_invalida", "La salida debe ser posterior a la entrada y no futura.", 422)
        repositorio.insertar_salida(
            cursor, salida_id, entrada_id, identificar(usuario["id"]), salida_en, motivo=motivo.strip()
        )
        return salida_publica(repositorio.obtener_salida(cursor, salida_id))


def _listar_visitas(cursor, ahora):
    filas = repositorio.listar_visitas_abiertas(cursor)
    historiales = {}
    permanencias = {}
    for fila in filas:
        sede = fila["sede_id"]
        if sede not in historiales:
            historial = repositorio.listar_duraciones_confiables(
                cursor, desde_bytes(sede), ahora - timedelta(weeks=8), ahora
            )
            historiales[sede] = historial
            permanencias[sede] = calcular_permanencia_habitual(tuple(visita["minutos"] for visita in historial))
    visitas = []
    for fila in filas:
        duracion = max(0, int((ahora - fila["registrada_en"].replace(tzinfo=UTC)).total_seconds()))
        minutos = duracion // 60
        habitual = calcular_permanencia_habitual(
            tuple(
                visita["minutos"] for visita in historiales[fila["sede_id"]] if visita["socio_id"] == fila["socio_id"]
            )
        )
        por_conciliar, _ = es_visita_por_conciliar(minutos, permanencias[fila["sede_id"]])
        visitas.append(
            {
                "id": str(desde_bytes(fila["entrada_id"])),
                "socio_id": str(desde_bytes(fila["socio_id"])),
                "nombre": fila["nombre"],
                "cedula": fila["cedula"],
                "entrada": fila["registrada_en"].replace(tzinfo=UTC).isoformat(),
                "entrada_local": fila["registrada_en"]
                .replace(tzinfo=UTC)
                .astimezone(ZoneInfo(fila["zona_horaria"]))
                .isoformat(),
                "duracion": duracion,
                "minutos": minutos,
                "permanencia_habitual": asdict(habitual),
                "por_conciliar": por_conciliar,
                "permanencia_habitual_sede": asdict(permanencias[fila["sede_id"]]),
            }
        )
    return sorted(visitas, key=lambda visita: not visita["por_conciliar"])


def listar_visitas():
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        return _listar_visitas(cursor, ahora)


def consultar_ocupacion():
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        sede = repositorio.obtener_sede(cursor)
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        visitas = _listar_visitas(cursor, ahora)
        return {
            "sede_id": str(desde_bytes(sede["id"])),
            "version": repositorio.obtener_version(cursor, ahora),
            "ocupacion_registrada": repositorio.contar_ocupacion_registrada(cursor, desde_bytes(sede["id"])),
            "aforo_maximo": sede["aforo_maximo"],
            "por_conciliar": sum(visita["por_conciliar"] for visita in visitas),
        }


def listar_socios():
    with transaccion() as cursor:
        filas = repositorio.listar_socios_activos(cursor)
    return [{"id": str(desde_bytes(fila["id"])), "nombre": fila["nombre"], "cedula": fila["cedula"]} for fila in filas]


def consultar_visitas():
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        version = repositorio.obtener_version(cursor, ahora)
        return {"visitas": _listar_visitas(cursor, ahora), "version": version}


def consultar_mejores_horarios():
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        sede = repositorio.obtener_sede(cursor)
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        zona = ZoneInfo(sede["zona_horaria"])
        ahora_local = ahora.astimezone(zona).replace(tzinfo=None)
        desde = (ahora_local - timedelta(weeks=8)).replace(tzinfo=zona).astimezone(UTC)
        filas = repositorio.listar_visitas_confiables(cursor, desde_bytes(sede["id"]), desde, ahora)
        visitas = tuple(
            tuple(
                fila[campo].replace(tzinfo=UTC).astimezone(zona).replace(tzinfo=None)
                for campo in ("registrada_en", "salida_registrada_en")
            )
            for fila in filas
        )
        horario_json = json.loads(sede["horario"]) if isinstance(sede["horario"], (str, bytes)) else sede["horario"]
        horario = tuple(
            sorted((int(dia), tuple(tuple(franja) for franja in franjas)) for dia, franjas in horario_json.items())
        )
        return asdict(calcular_mejores_horarios(visitas, ahora_local, horario))
