"""Vectores de la regla de reservas y lista de espera, sin base ni reloj."""

import itertools

import pytest

from gimnasio.reglas.clases import cambios_de_estado, estado_reservas


def reserva(id_, minuto):
    return {"id": id_, "solicitada_en": f"2026-10-27T10:{minuto:02d}:00Z"}


A, B, C, D = (reserva(letra, minuto) for minuto, letra in enumerate("abcd"))


def espera(*ids):
    return [{"id": id_, "posicion": posicion} for posicion, id_ in enumerate(ids, start=1)]


@pytest.mark.parametrize(
    "cupo,reservas,con_lugar,en_espera",
    [
        (3, [A], ["a"], []),
        (2, [A, B], ["a", "b"], []),
        (2, [A, B, C, D], ["a", "b"], ["c", "d"]),
        (10, [A, B], ["a", "b"], []),
        (2, [], [], []),
    ],
)
def test_cupo_y_espera(cupo, reservas, con_lugar, en_espera):
    assert estado_reservas(cupo, reservas) == {"con_lugar": con_lugar, "en_espera": espera(*en_espera)}


def test_quitar_a_quien_tiene_lugar_sube_al_primero_en_espera():
    estado = estado_reservas(2, [B, C, D])
    assert estado["con_lugar"] == ["b", "c"]
    assert estado["en_espera"] == espera("d")


def test_bajar_y_subir_el_cupo():
    reservas = [A, B, C]
    assert estado_reservas(1, reservas) == {"con_lugar": ["a"], "en_espera": espera("b", "c")}
    assert estado_reservas(3, reservas) == {"con_lugar": ["a", "b", "c"], "en_espera": []}


def test_cupo_menor_que_uno_falla():
    for cupo in (0, -1):
        with pytest.raises(ValueError, match="cupo"):
            estado_reservas(cupo, [A])


def test_orden_estable_por_id_y_sin_depender_de_la_entrada():
    mismas = [{"id": id_, "solicitada_en": "2026-10-27T10:00:00Z"} for id_ in ("c", "a", "b")]
    esperado = {"con_lugar": ["a"], "en_espera": espera("b", "c")}
    for permutacion in itertools.permutations(mismas):
        assert estado_reservas(1, list(permutacion)) == esperado


def test_quitar_reserva_en_espera_no_cambia_quien_tiene_lugar():
    completo = estado_reservas(2, [A, B, C, D])
    sin_c = estado_reservas(2, [A, B, D])
    assert sin_c["con_lugar"] == completo["con_lugar"]
    assert sin_c["en_espera"] == espera("d")


def test_cambios_al_liberarse_un_lugar():
    antes = estado_reservas(2, [A, B, C])
    despues = estado_reservas(2, [B, C])
    assert cambios_de_estado(antes, despues) == {"pasaron_a_tener_lugar": ["c"], "volvieron_a_espera": []}


def test_cambios_al_bajar_el_cupo():
    antes = estado_reservas(3, [A, B, C])
    despues = estado_reservas(1, [A, B, C])
    assert cambios_de_estado(antes, despues) == {"pasaron_a_tener_lugar": [], "volvieron_a_espera": ["b", "c"]}


def test_cambios_ignora_reservas_nuevas_y_sin_cambio():
    antes = estado_reservas(1, [A])
    despues = estado_reservas(1, [A, B])
    assert cambios_de_estado(antes, despues) == {"pasaron_a_tener_lugar": [], "volvieron_a_espera": []}
