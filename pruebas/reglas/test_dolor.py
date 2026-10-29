"""Vectores del freno 1 y contrato de las zonas con la silueta."""

import json
from dataclasses import replace
from pathlib import Path

from gimnasio.comun.tipos import ZONAS_CUERPO, EjercicioCatalogo
from gimnasio.reglas.sesion import proponer_sesion
from pruebas.reglas.test_progresion import entrada


def datos_dolor():
    original = EjercicioCatalogo(
        "sentadilla",
        "Sentadilla ficticia",
        None,
        "barra",
        "sentadilla",
        ("gluteos", "cuadriceps", "rodillas"),
        ("cajon",),
    )
    cajon = replace(
        original,
        ejercicio_id="cajon",
        nombre="Sentadilla en cajón ficticia",
        equipo="cajon",
        zonas=("gluteos", "cuadriceps"),
        alternativas=(),
    )
    from decimal import Decimal

    return replace(entrada(), catalogo=(replace(original, incremento_carga=Decimal("2.5")), cajon))


def test_freno_1_dolor_bloquea_suba():
    actual = proponer_sesion(replace(datos_dolor(), dolores_actuales=("rodillas",)))
    siguiente = proponer_sesion(replace(datos_dolor(), dolores_anteriores=("rodillas",)))
    subsiguiente = proponer_sesion(datos_dolor())
    assert actual.prescripcion[0].carga == siguiente.prescripcion[0].carga == 40
    assert actual.prescripcion[0].ejercicio_hecho_id == "cajon"
    assert siguiente.prescripcion[0].ejercicio_hecho_id is None
    assert "dolor_reportado" in actual.frenos and "dolor_reportado" in siguiente.frenos
    assert subsiguiente.prescripcion[0].carga > 40
    assert "dolor_reportado" not in subsiguiente.frenos


def test_sustitucion_y_ejercicio_quitado_tienen_explicacion():
    for zonas, series, hecho in ((["rodillas"], 3, "cajon"), (["cuadriceps"], 0, None)):
        propuesta = proponer_sesion(replace(datos_dolor(), dolores_actuales=tuple(zonas)))
        assert propuesta.prescripcion[0].series == series
        assert propuesta.prescripcion[0].ejercicio_hecho_id == hecho
        razon = next(r for r in propuesta.explicacion if r.regla == "dolor_reportado")
        assert ("no involucra" if hecho else "Se quita") in dict(razon.datos)["explicacion"]


def test_zonas_backend_coinciden_con_vector_compartido():
    vector = Path(__file__).resolve().parents[1] / "vectores" / "zonas_cuerpo.json"
    assert tuple(json.loads(vector.read_text(encoding="utf-8"))) == ZONAS_CUERPO
