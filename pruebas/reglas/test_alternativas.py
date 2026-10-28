"""Vectores de sustitución por máquina ocupada."""

from gimnasio.comun.tipos import EjercicioCatalogo
from gimnasio.reglas.alternativas import elegir_alternativas


def ejercicio(identificador, equipo="mancuernas", zonas=("cuadriceps",), patron="sentadilla"):
    return EjercicioCatalogo(identificador, identificador, None, equipo, patron, zonas)


def test_otro_equipo_orden_y_razon():
    original = EjercicioCatalogo(
        "original",
        "Original",
        None,
        "barra",
        "sentadilla",
        ("cuadriceps",),
        ("segunda", "primera", "mismo", "otra_zona", "otro_patron"),
    )
    catalogo = (
        original,
        ejercicio("primera"),
        ejercicio("segunda"),
        ejercicio("mismo", "barra"),
        ejercicio("otra_zona", zonas=("pecho",)),
        ejercicio("otro_patron", patron="empuje"),
    )
    alternativas, razon = elegir_alternativas("original", catalogo)
    assert [e.ejercicio_id for e in alternativas] == ["primera", "segunda"]
    assert dict(razon.datos)["ejercicio_hecho_id"] == "primera"
    assert elegir_alternativas("original", catalogo, ejercicios_excluidos=("primera",))[0] == (catalogo[2],)
    assert elegir_alternativas("original", catalogo, zonas_excluidas=("cuadriceps",)) == ((), None)
    assert elegir_alternativas("inexistente", catalogo) == ((), None)
    assert elegir_alternativas("original", (original,)) == ((), None)
