"""Consulta del catálogo, edición de alternativas y cambios de estado de equipos."""

from flask import Blueprint, jsonify, request

from gimnasio.permisos.matriz import puede
from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.programas import servicio

bp = Blueprint("programas", __name__, url_prefix="/api")


@bp.get("/programas/plantillas")
@requiere("programas.editar", "plantillas.administrar")
def listar_plantillas():
    return jsonify(
        {
            "plantillas": servicio.listar_plantillas(
                incluir_archivadas=puede(usuario_actual()["rol"], "plantillas.administrar")
            )
        }
    )


@bp.post("/programas/plantillas")
@requiere("plantillas.administrar")
def crear_plantilla():
    return jsonify({"plantilla": servicio.guardar_plantilla(request.get_json(silent=True))}), 201


@bp.put("/programas/plantillas/<plantilla_id>")
@requiere("plantillas.administrar")
def editar_plantilla(plantilla_id):
    return jsonify({"plantilla": servicio.guardar_plantilla(request.get_json(silent=True), plantilla_id)})


@bp.post("/programas/plantillas/<plantilla_id>/archivar")
@requiere("plantillas.administrar")
def archivar_plantilla(plantilla_id):
    return jsonify({"plantilla": servicio.archivar_plantilla(plantilla_id)})


@bp.get("/socios/<socio_id>/programa")
@requiere("programas.editar")
def programa_vigente(socio_id):
    return jsonify({"programa": servicio.programa_vigente(socio_id, usuario_actual())})


@bp.post("/socios/<socio_id>/programas")
@requiere("programas.editar")
def publicar_programa(socio_id):
    return jsonify(
        {"programa": servicio.publicar_programa(socio_id, request.get_json(silent=True), usuario_actual())}
    ), 201


@bp.get("/equipos")
@requiere("equipos.gestionar")
def listar_equipos():
    return jsonify({"equipos": servicio.listar_equipos()})


@bp.post("/equipos/<equipo_id>/estado")
@requiere("equipos.gestionar")
def cambiar_estado_equipo(equipo_id):
    return jsonify(
        {"equipo": servicio.cambiar_estado_equipo(equipo_id, request.get_json(silent=True), usuario_actual())}
    )


@bp.get("/ejercicios")
@requiere("alternativas.editar", "programas.editar")
def listar_ejercicios():
    return jsonify({"ejercicios": servicio.listar_ejercicios()})


@bp.post("/ejercicios/<ejercicio_id>/alternativas")
@requiere("alternativas.editar")
def reemplazar_alternativas(ejercicio_id):
    return jsonify({"ejercicio": servicio.reemplazar_alternativas(ejercicio_id, request.get_json(silent=True))})


@bp.get("/socios/<socio_id>/programa/cargas-sugeridas")
@requiere("programas.editar")
def cargas_sugeridas(socio_id):
    return jsonify(
        {"cargas": servicio.cargas_sugeridas(socio_id, request.args.get("ejercicios", ""), usuario_actual())}
    )
