"""Vectores del freno 2, con alternativas y frenos simultáneos."""

from dataclasses import replace

import pytest

from gimnasio.comun.tipos import RestriccionSalud
from gimnasio.reglas.restricciones import excluido
from gimnasio.reglas.sesion import proponer_sesion
from pruebas.reglas.test_dolor import datos_dolor


@pytest.mark.parametrize("tipo", ["catalogo", "planificado", "zona", "patron", "sin_restriccion", "otro_ejercicio"])
@pytest.mark.parametrize("sin_identificador_catalogo", [False, True])
def test_freno_2_sin_ejercicio_en_catalogo(tipo, sin_identificador_catalogo):
    datos = datos_dolor()
    sesion = datos.programa.sesiones[0]
    planificado = sesion.ejercicios[0]
    if sin_identificador_catalogo:
        planificado = replace(planificado, ejercicio_catalogo_id=None)
    restricciones = {
        "catalogo": RestriccionSalud(ejercicio_id=planificado.ejercicio_catalogo_id or planificado.ejercicio_id),
        "planificado": RestriccionSalud(ejercicio_id=planificado.ejercicio_id),
        "zona": RestriccionSalud(zona="rodillas"),
        "patron": RestriccionSalud(patron_movimiento="sentadilla"),
        "otro_ejercicio": RestriccionSalud(ejercicio_id="otro"),
    }
    propuesta = proponer_sesion(
        replace(
            datos,
            programa=replace(datos.programa, sesiones=(replace(sesion, ejercicios=(planificado,)),)),
            catalogo=(),
            restricciones=() if tipo == "sin_restriccion" else (restricciones[tipo],),
        )
    )
    prescripcion = propuesta.prescripcion[0]
    if tipo in ("sin_restriccion", "otro_ejercicio"):
        assert prescripcion.series == planificado.series
        assert "restriccion_salud" not in propuesta.frenos
    else:
        assert prescripcion.series == 0
        assert prescripcion.ejercicio_hecho_id is None
        assert "restriccion_salud" in propuesta.frenos
        razon = next(r for r in propuesta.explicacion if r.regla == "restriccion_salud")
        assert dict(razon.datos)["explicacion"] == (
            "Se quita el ejercicio por una restricción registrada por tu entrenador."
        )


@pytest.mark.parametrize("tipo", ["ejercicio", "patron", "zona"])
@pytest.mark.parametrize("con_alternativa", [False, True])
def test_freno_2_restriccion_nunca_propuesta(tipo, con_alternativa):
    datos = datos_dolor()
    original, alternativa = datos.catalogo
    alternativa = replace(alternativa, zonas=original.zonas)
    restricciones = {
        "ejercicio": RestriccionSalud(ejercicio_id=original.ejercicio_id),
        "patron": RestriccionSalud(patron_movimiento=original.patron_movimiento),
        "zona": RestriccionSalud(zona="rodillas"),
    }
    if tipo == "zona":
        alternativa = replace(alternativa, zonas=("gluteos", "cuadriceps"))
    restriccion = replace(restricciones[tipo], descripcion="sin carga axial en zona lumbar")
    catalogo = (original, alternativa) if con_alternativa else (original,)
    propuesta = proponer_sesion(replace(datos, catalogo=catalogo, restricciones=(restriccion,)))
    prescripcion = propuesta.prescripcion[0]
    assert "restriccion_salud" in propuesta.frenos
    if prescripcion.series:
        hecho = next(e for e in catalogo if e.ejercicio_id == prescripcion.ejercicio_hecho_id)
        assert not excluido(hecho, (restriccion,))
    else:
        assert prescripcion.ejercicio_hecho_id is None
    assert bool(prescripcion.series) == (con_alternativa and tipo != "patron")
    assert restriccion.descripcion not in str(propuesta.explicacion)
    assert "restricción registrada por tu entrenador" in str(propuesta.explicacion)


def test_alternativa_por_dolor_tambien_respeta_todas_las_restricciones():
    datos = replace(
        datos_dolor(), dolores_actuales=("rodillas",), restricciones=(RestriccionSalud(ejercicio_id="cajon"),)
    )
    propuesta = proponer_sesion(datos)
    assert propuesta.prescripcion[0].series == 0
    assert set(propuesta.frenos) == {"dolor_reportado", "restriccion_salud"}


def test_alternativa_no_puede_infringir_otra_restriccion():
    datos = replace(
        datos_dolor(),
        restricciones=(
            RestriccionSalud(zona="rodillas"),
            RestriccionSalud(ejercicio_id="cajon"),
        ),
    )
    assert proponer_sesion(datos).prescripcion[0].series == 0
