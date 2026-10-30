"""Vectores de sustitución por máquina ocupada."""

from gimnasio.comun.tipos import EjercicioCatalogo
from gimnasio.reglas.alternativas import elegir_alternativas


def test_equipos_fuera_de_servicio_se_descartan_para_todos_los_motivos():
    from dataclasses import replace

    original = replace(ejercicio("original", "barra"), alternativas=("primera", "segunda"))
    catalogo = (original, ejercicio("primera", "prensa"), ejercicio("segunda", "mancuernas"))
    for motivo in ("maquina_ocupada", "dolor_reportado", "equipo_fuera_de_servicio", "restriccion_salud"):
        alternativas, razon = elegir_alternativas(
            "original", catalogo, motivo=motivo, equipos_fuera_de_servicio=frozenset({"prensa"})
        )
        assert alternativas == (catalogo[2],)
        assert razon.regla == motivo
        assert elegir_alternativas(
            "original", catalogo, motivo=motivo, equipos_fuera_de_servicio=frozenset({"prensa", "mancuernas"})
        ) == ((), None)


def test_dolor_descarta_equipo_fuera_de_servicio_con_zonas_reducidas():
    from dataclasses import replace

    original = replace(ejercicio("original", "barra", ("gluteos", "rodillas")), alternativas=("primera", "segunda"))
    catalogo = (
        original,
        ejercicio("primera", "prensa", ("gluteos",)),
        ejercicio("segunda", "mancuernas", ("gluteos",)),
    )
    alternativas, _ = elegir_alternativas(
        "original",
        catalogo,
        zonas_excluidas=("rodillas",),
        motivo="dolor_reportado",
        equipos_fuera_de_servicio=frozenset({"prensa"}),
    )
    assert alternativas == (catalogo[2],)


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


def test_dolor_exige_zonas_reducidas_no_vacias_sin_agregar_zonas():
    from dataclasses import replace

    original = replace(
        ejercicio("original", equipo="barra", zonas=("gluteos", "cuadriceps", "rodillas")),
        alternativas=("con_dolor", "agrega", "vacia", "reducida"),
    )
    reducida = ejercicio("reducida", equipo="cajon", zonas=("gluteos", "cuadriceps"))
    catalogo = (
        original,
        reducida,
        ejercicio("con_dolor", zonas=original.zonas),
        ejercicio("agrega", zonas=("gluteos", "isquiotibiales")),
        ejercicio("vacia", zonas=()),
    )
    alternativas, razon = elegir_alternativas(
        "original", catalogo, zonas_excluidas=("rodillas",), motivo="dolor_reportado"
    )
    assert alternativas == (reducida,)
    assert razon.regla == "dolor_reportado"
    assert dict(razon.datos)["ejercicio_hecho_id"] == "reducida"
    assert dict(razon.datos)["explicacion"] == (
        "reducida conserva el patrón de movimiento y no involucra la zona con dolor."
    )
    assert reducida not in elegir_alternativas("original", catalogo)[0]
