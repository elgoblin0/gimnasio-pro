"""Vectores de prioridad de la bandeja, sin dependencias del servicio."""

from copy import deepcopy

from gimnasio.comun.tipos import GrupoBandeja, MotivoBandeja, SocioBandeja
from gimnasio.reglas.bandeja import GRUPOS, priorizar_bandeja


def socio(identificador, *motivos):
    return SocioBandeja(identificador, tuple(MotivoBandeja(tipo, fecha) for tipo, fecha in motivos))


def test_orden_entre_grupos():
    entrada = [socio(str(i), (tipo, "2026-10-30")) for i, tipo in enumerate(reversed(GRUPOS))]
    salida = priorizar_bandeja(entrada)
    assert [g.tipo for g in salida] == list(GRUPOS)
    assert [g.socios[0].id for g in salida] == ["5", "4", "3", "2", "1", "0"]


def test_antiguedad_empate_y_varios_motivos_sin_mutar():
    entrada = [
        socio("c", ("aviso_seguridad", "2026-10-30"), ("sin_programa", "2026-01-01")),
        socio("b", ("aviso_seguridad", "2026-10-29")),
        socio("a", ("aviso_seguridad", "2026-10-29"), ("aviso_seguridad", "2026-10-30")),
        socio("sin_motivos"),
    ]
    antes = deepcopy(entrada)
    salida = priorizar_bandeja(entrada)
    assert [s.id for s in salida[0].socios] == ["a", "b", "c"]
    assert salida[0].socios[2].motivos == entrada[0].motivos
    assert all(not g.socios for g in salida[1:])
    assert entrada == antes
    assert salida[0].socios[0].explicacion[0].regla == "prioridad_bandeja"


def test_lista_vacia():
    assert priorizar_bandeja([]) == tuple(GrupoBandeja(tipo, ()) for tipo in GRUPOS)
