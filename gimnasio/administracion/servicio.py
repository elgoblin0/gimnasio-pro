"""Consulta y cambios de configuración con historial inmutable."""

import json
import re
from datetime import UTC

from flask import current_app

from gimnasio.administracion import repositorio
from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.visitas.servicio import ocupacion_en_transaccion


def validar_cambio(datos):
    if not isinstance(datos, dict):
        raise ErrorDeDominio("cuerpo_invalido", "Enviá aforo máximo, horario y motivo.", 422)
    aforo = datos.get("aforo_maximo")
    if type(aforo) is not int or not 0 < aforo <= 65535:
        raise ErrorDeDominio("aforo_invalido", "El aforo máximo debe ser un entero mayor que cero.", 422)
    motivo = datos.get("motivo")
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo) > 500:
        raise ErrorDeDominio("motivo_invalido", "El motivo es obligatorio y admite hasta 500 caracteres.", 422)
    horario = datos.get("horario")
    if not isinstance(horario, dict):
        raise ErrorDeDominio("horario_invalido", "Enviá el horario por día de la semana.", 422)
    for dia, intervalos in horario.items():
        if dia not in {str(numero) for numero in range(1, 8)} or not isinstance(intervalos, list):
            raise ErrorDeDominio("horario_invalido", "El horario usa días del 1 al 7 e intervalos.", 422)
        anterior = "00:00"
        for intervalo in intervalos:
            if (
                not isinstance(intervalo, list)
                or len(intervalo) != 2
                or any(
                    not isinstance(hora, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", hora)
                    for hora in intervalo
                )
                or not anterior <= intervalo[0] < intervalo[1]
            ):
                raise ErrorDeDominio("horario_invalido", "Usá intervalos HH:MM ordenados y sin superposición.", 422)
            anterior = intervalo[1]
    return aforo, horario, motivo.strip()


def _horario(valor):
    return json.loads(valor) if isinstance(valor, (str, bytes)) else valor


def _consultar(cursor, sede):
    sede_id = desde_bytes(sede["id"])
    return {
        "aforo_maximo": sede["aforo_maximo"],
        "horario": _horario(sede["horario"]),
        "ocupacion_registrada": ocupacion_en_transaccion(cursor, sede_id),
        "historial": [
            {
                "id": str(desde_bytes(fila["id"])),
                "aforo_maximo": fila["aforo_maximo"],
                "horario": _horario(fila["horario"]),
                "motivo": fila["motivo"],
                "autor_id": str(desde_bytes(fila["autor_id"])),
                "autor": fila["autor"],
                "registrado_en": fila["registrado_en"].replace(tzinfo=UTC).isoformat(),
            }
            for fila in repositorio.listar_cambios(cursor, sede_id)
        ],
    }


def _sede(cursor, *, bloquear=False):
    sede = repositorio.obtener_sede(cursor, bloquear=bloquear)
    if sede is None:
        raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
    return sede


def consultar_sede():
    with transaccion() as cursor:
        return _consultar(cursor, _sede(cursor))


def cambiar_sede(datos, usuario):
    aforo, horario, motivo = validar_cambio(datos)
    if current_app.config["MODO_DEMO"] and not 30 <= aforo <= 120:
        raise ErrorDeDominio(
            "aforo_fuera_de_rango_demo", "En modo demo el aforo máximo admite de 30 a 120 personas.", 422
        )
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        sede = _sede(cursor, bloquear=True)
        repositorio.registrar_cambio(
            cursor, nuevo_id(), desde_bytes(sede["id"]), aforo, horario, motivo, desde_texto(usuario["id"]), ahora
        )
        sede.update(aforo_maximo=aforo, horario=horario)
        return _consultar(cursor, sede)
