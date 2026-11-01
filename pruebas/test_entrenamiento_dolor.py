"""La edición de alternativas conserva las sustituciones vigentes seguras."""

import json

import pytest

from gimnasio.comun.ids import nuevo_id
from gimnasio.comun.tipos import EjercicioCatalogo, RestriccionSalud
from gimnasio.entrenamiento import servicio


@pytest.mark.parametrize("precargadas", [False, True])
@pytest.mark.parametrize("freno", [None, "dolor", "restriccion"])
def test_sustitucion_vigente_fuera_de_alternativas(monkeypatch, reloj_fijo, precargadas, freno):
    original_id, hecho_id, planificado_id, sesion_id = (nuevo_id(reloj_fijo) for _ in range(4))
    original = EjercicioCatalogo(str(original_id), "Original", 1, "barra", "sentadilla", ("rodillas", "gluteos"), ())
    hecho = EjercicioCatalogo(str(hecho_id), "Sustituto", 1, "banda", "sentadilla", ("gluteos",), ())
    catalogos = {str(original_id): (original,)}
    monkeypatch.setattr(
        servicio,
        "catalogo_ejercicio",
        lambda cursor, ejercicio: (hecho,) if ejercicio["ejercicio_id"] == str(hecho_id) else (original,),
    )
    monkeypatch.setattr(
        servicio.repositorio, "sustitucion_vigente", lambda *args: {"ejercicio_hecho_id": hecho_id.bytes}
    )
    efectiva = {
        "ejercicios": json.dumps(
            [
                {
                    "id": str(planificado_id),
                    "ejercicio_id": str(original_id),
                    "objetivos": {
                        "series": 2,
                        "repeticiones_minimas": 8,
                        "repeticiones_maximas": 12,
                        "carga": 10,
                        "rir_objetivo": 2,
                        "descanso": 60,
                    },
                    "explicacion": [],
                }
            ]
        ),
    }
    if precargadas:
        efectiva["sustituciones_vigentes"] = json.dumps({str(planificado_id): str(hecho_id)})
    resultado = servicio.proyectar_dolor(
        object(),
        {"id": sesion_id.bytes},
        efectiva,
        zonas=("rodillas", "gluteos") if freno == "dolor" else ("rodillas",),
        catalogos=catalogos,
        restricciones=(RestriccionSalud(zona="gluteos"),) if freno == "restriccion" else (),
        equipos=frozenset(),
    )[0]
    assert resultado["objetivos"]["series"] == (0 if freno == "dolor" else 2)
    assert resultado.get("no_disponible", False) is (freno == "restriccion")
    assert resultado["ejercicio_hecho_id"] == (None if freno else str(hecho_id))
    # La sustitución registrada no vuelve a ofrecerse como alternativa nueva.
    assert catalogos[str(original_id)] == (original,)
