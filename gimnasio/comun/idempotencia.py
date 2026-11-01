"""Escrituras y respuestas en una misma transacción de MySQL (ADR 0004).

Los servicios deben usar comun.bd.transaccion, sin commit directo ni efectos externos.
El candado pertenece a la conexión: un proceso caído lo libera y MySQL revierte la escritura.
"""

import hashlib
import json
from base64 import b64decode, b64encode
from datetime import timedelta
from uuid import UUID

from flask import Response, g, request

from gimnasio.comun.bd import conexion_actual
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.reloj import reloj_actual

METODOS_QUE_CAMBIAN = {"POST", "PUT", "PATCH", "DELETE"}


def purgar(cursor, ahora):
    """Borra solo claves con más de siete días; participa de la transacción del llamador."""
    cursor.execute("DELETE FROM solicitudes_idempotentes WHERE creada_en < %s", (ahora - timedelta(days=7),))
    return cursor.rowcount


def registrar_idempotencia(app, obtener_usuario):
    """Recibe la consulta de usuario desde la composición; comun no importa dominio.

    Se registra después de los controles de sesión y CSRF. Todas las rutas de escritura
    quedan cubiertas automáticamente, salvo las rutas de sesión del ADR 0004.
    """

    @app.before_request
    def preparar():
        if request.method not in METODOS_QUE_CAMBIAN or request.endpoint is None:
            return None
        if request.endpoint in {"permisos.iniciar", "permisos.cerrar", "permisos.entrar_como"}:
            return None
        texto = request.headers.get("Idempotency-Key")
        if not texto:
            raise ErrorDeDominio("falta_clave", "Falta Idempotency-Key.", 428)
        try:
            clave = UUID(texto).bytes
        except ValueError as error:
            raise ErrorDeDominio("clave_invalida", "Idempotency-Key debe ser un UUID.", 422) from error
        usuario = obtener_usuario()
        if usuario is None:
            raise ErrorDeDominio("sin_sesion", "Tenés que iniciar sesión.", 401)
        usuario_id = UUID(usuario["id"]).bytes
        conexion = conexion_actual()
        huella = hashlib.sha256(request.get_data()).digest()
        nombre = hashlib.sha256(conexion.database.encode() + usuario_id + clave).hexdigest()
        with conexion.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0) AS obtenido", (nombre,))
            if cursor.fetchone()["obtenido"] != 1:
                raise ErrorDeDominio("solicitud_en_curso", "Hay una solicitud con esa clave en curso.", 409)
            g.candado_idempotencia = nombre
            # La consulta del usuario pudo abrir una lectura consistente anterior al candado.
            conexion.rollback()
            ahora = reloj_actual().ahora()
            purgar(cursor, ahora)
            conexion.commit()
            cursor.execute(
                "SELECT huella_cuerpo, estado_http, respuesta FROM solicitudes_idempotentes "
                "WHERE usuario_id = %s AND clave = %s",
                (usuario_id, clave),
            )
            fila = cursor.fetchone()
            if fila:
                conexion.commit()
                if fila["huella_cuerpo"] != huella:
                    raise ErrorDeDominio("clave_reutilizada", "La clave ya corresponde a otra solicitud.", 422)
                guardada = json.loads(fila["respuesta"])
                return Response(
                    b64decode(guardada["cuerpo"]), status=fila["estado_http"], headers=guardada["encabezados"]
                )
            # La búsqueda sin resultado también abre una lectura consistente en MySQL.
            # Cerrarla permite que el servicio vea el estado confirmado tras esperar sus candados.
            # Todavía no se escribió ningún hecho ni se activó la transacción de la operación.
            conexion.commit()
        g.solicitud_idempotente = (clave, usuario_id, huella, ahora)
        g.idempotencia_activa = True
        return None

    @app.after_request
    def guardar(respuesta):
        solicitud = g.pop("solicitud_idempotente", None)
        if solicitud is None:
            return respuesta
        conexion = conexion_actual()
        # Errores no deben confirmar escrituras parciales, ni quedar como éxitos al reintentar.
        if respuesta.status_code >= 400:
            conexion.rollback()
        if respuesta.status_code >= 500:
            return respuesta
        saneada = g.pop("respuesta_para_reintento", None)
        cuerpo = json.dumps(saneada).encode() if isinstance(saneada, dict) else respuesta.get_data()
        guardada = json.dumps(
            {
                "cuerpo": b64encode(cuerpo).decode("ascii"),
                "encabezados": [(k, v) for k, v in respuesta.headers if k.lower() != "set-cookie"],
            }
        ).encode()
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO solicitudes_idempotentes "
                "(clave, usuario_id, huella_cuerpo, creada_en, estado_http, respuesta) VALUES (%s, %s, %s, %s, %s, %s)",
                (*solicitud, respuesta.status_code, guardada),
            )
        conexion.commit()
        return respuesta

    @app.teardown_request
    def terminar(_error):
        nombre = g.pop("candado_idempotencia", None)
        g.pop("idempotencia_activa", None)
        if nombre is not None:
            conexion = conexion_actual()
            conexion.rollback()
            with conexion.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (nombre,))
                cursor.fetchone()
