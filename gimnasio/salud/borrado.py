"""Borrado de datos de salud: única excepción autorizada al historial que solo agrega (ADR 0003 y 0025).

Conserva filas e ids: las sesiones, las series y los avisos siguen existiendo, sin datos de salud legibles.
"""

import json

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.salud import repositorio
from gimnasio.salud.servicio import tiene_consentimiento_salud

# La semilla de la demo crea al socio dedicado al borrado con esta cédula ficticia.
CEDULA_SOCIO_BORRADO_DEMO = "97000000"
CONFIRMACION = "BORRAR"
REGLAS_DE_SALUD = {"dolor_reportado", "restriccion_salud"}
DATOS_CONSERVADOS = {"ejercicio_id", "ejercicio_hecho_id"}


def sin_datos_salud(valor):
    """Copia una explicación guardada: las razones de salud conservan lo mismo que muestra el ADR 0024."""
    if isinstance(valor, list):
        return [sin_datos_salud(elemento) for elemento in valor]
    if not isinstance(valor, dict):
        return valor
    if valor.get("regla") in REGLAS_DE_SALUD:
        datos = valor.get("datos")
        return {
            **{clave: valor[clave] for clave in ("regla", "version") if clave in valor},
            "datos": {c: d for c, d in datos.items() if c in DATOS_CONSERVADOS} if isinstance(datos, dict) else {},
        }
    return {clave: sin_datos_salud(dato) for clave, dato in valor.items()}


def _limpiar_columnas(filas, columnas):
    """Parámetros para reescribir solo las filas que cambian, en el orden de `columnas` más el id."""
    cambios = []
    for fila in filas:
        originales = [json.loads(fila[columna]) for columna in columnas]
        limpias = [sin_datos_salud(original) for original in originales]
        if limpias != originales:
            cambios.append((*(json.dumps(limpia, ensure_ascii=False) for limpia in limpias), fila["id"]))
    return cambios


def _anonimizar_textos(cursor, socio):
    cursor.execute(
        """UPDATE revisiones_condicion r JOIN condiciones_salud c ON c.id=r.condicion_id
           SET r.nota=NULL WHERE c.socio_id=%s""",
        (socio,),
    )
    cursor.execute("UPDATE condiciones_salud SET descripcion=NULL,anonimizada=TRUE WHERE socio_id=%s", (socio,))
    cursor.execute("UPDATE avisos_personal SET texto=NULL,anonimizada=TRUE WHERE socio_id=%s", (socio,))
    cursor.execute(
        """UPDATE restricciones_salud
           SET ejercicio_id=NULL,patron_movimiento=NULL,zona=NULL,descripcion=NULL,anonimizada=TRUE
           WHERE socio_id=%s""",
        (socio,),
    )
    cursor.execute("UPDATE dolores_reportados SET zona=NULL,anonimizada=TRUE WHERE socio_id=%s", (socio,))
    cursor.execute(
        """UPDATE revisiones_aviso r JOIN avisos_entrenador a ON a.id=r.aviso_id
           SET r.nota=NULL WHERE a.socio_id=%s""",
        (socio,),
    )


def _anonimizar_explicaciones(cursor, socio):
    cursor.execute("SELECT id,explicacion FROM avisos_entrenador WHERE socio_id=%s FOR UPDATE", (socio,))
    cambios = _limpiar_columnas(cursor.fetchall(), ("explicacion",))
    if cambios:
        cursor.executemany("UPDATE avisos_entrenador SET explicacion=%s WHERE id=%s", cambios)
    cursor.execute(
        """SELECT p.id,p.ejercicios,p.explicacion,p.frenos FROM prescripciones_efectivas p
           JOIN sesiones_realizadas s ON s.id=p.sesion_realizada_id WHERE s.socio_id=%s FOR UPDATE""",
        (socio,),
    )
    cambios = _limpiar_columnas(cursor.fetchall(), ("ejercicios", "explicacion", "frenos"))
    if cambios:
        cursor.executemany(
            "UPDATE prescripciones_efectivas SET ejercicios=%s,explicacion=%s,frenos=%s WHERE id=%s", cambios
        )
    cursor.execute(
        """SELECT a.id,a.ejercicios,a.explicacion FROM prescripciones_ajustadas a
           JOIN sesiones_realizadas s ON s.id=a.sesion_realizada_id WHERE s.socio_id=%s FOR UPDATE""",
        (socio,),
    )
    cambios = _limpiar_columnas(cursor.fetchall(), ("ejercicios", "explicacion"))
    if cambios:
        cursor.executemany("UPDATE prescripciones_ajustadas SET ejercicios=%s,explicacion=%s WHERE id=%s", cambios)


def borrar_datos_salud(socio_id, datos, modo_demo):
    if not isinstance(datos, dict) or set(datos) != {"confirmacion"} or datos["confirmacion"] != CONFIRMACION:
        raise ErrorDeDominio("confirmacion_invalida", f"Escribí {CONFIRMACION} para confirmar el borrado.", 422)
    with transaccion() as cursor:
        # El mismo bloqueo que registrar dolores o consentimientos: nada se guarda en medio del borrado.
        repositorio.bloquear_socio(cursor, socio_id)
        if modo_demo and not repositorio.admite_borrado_en_demo(cursor, socio_id, CEDULA_SOCIO_BORRADO_DEMO):
            raise ErrorDeDominio(
                "borrado_no_disponible_demo",
                "En la demo, el borrado solo funciona con el socio dedicado y con los socios creados en ella.",
                403,
            )
        if tiene_consentimiento_salud(cursor, socio_id):
            raise ErrorDeDominio("consentimiento_vigente", "Revocá el consentimiento de salud antes de borrar.", 409)
        socio = a_bytes(socio_id)
        _anonimizar_textos(cursor, socio)
        _anonimizar_explicaciones(cursor, socio)
        # Las respuestas guardadas para reintentos repiten textos y zonas; se purgan igual a los 7 días.
        cursor.execute("DELETE FROM solicitudes_idempotentes WHERE usuario_id=%s", (socio,))
        identificador = nuevo_id()
        cursor.execute(
            "INSERT INTO borrados_salud (id,socio_id,registrado_en) VALUES (%s,%s,%s)",
            (a_bytes(identificador), socio, reloj_actual().ahora()),
        )
    return {"borrado_salud_id": str(identificador)}
