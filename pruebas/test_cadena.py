"""Pruebas de la lógica pura de la cadena de agentes (sin gh ni red)."""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar(nombre):
    especificacion = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


cadena = cargar("cadena")


def test_lee_las_dependencias_del_formato_de_la_plantilla():
    assert cadena.dependencias("Objetivo\n\nDepende de: #12, #13\n") == [12, 13]
    assert cadena.dependencias("Sin dependencias") == []
    assert cadena.dependencias(None) == []


def test_elige_el_issue_listo_mas_bajo_con_dependencias_cerradas():
    issues = [
        {"number": 30, "body": ""},
        {"number": 21, "body": "Depende de: #20"},
        {"number": 25, "body": "Depende de: #19"},
    ]
    cerrados = {19}
    assert cadena.elegir_siguiente(issues, cerrados.__contains__)["number"] == 25
    assert cadena.elegir_siguiente([{"number": 21, "body": "Depende de: #20"}], cerrados.__contains__) is None


def test_solo_las_ramas_de_la_cadena_tienen_numero_de_issue():
    assert cadena.numero_de_rama("codex/issue-42") == 42
    assert cadena.numero_de_rama("automatiza-cadena-agentes") is None


def test_detecta_las_rutas_sensibles_de_agents():
    assert cadena.es_sensible(["gimnasio/reglas/motor.py"])
    assert cadena.es_sensible(["docs/x.md", "migraciones/0012_algo.sql"])
    assert cadena.es_sensible(["gimnasio/comun/migrar.py"])
    assert not cadena.es_sensible(["gimnasio/comun/reloj.py", "gimnasio/static/js/app.js"])


def test_una_revision_sin_comentarios_en_linea_aprueba():
    assert cadena.revision_aprobada("Codex Review: hallazgos", 0)
    assert cadena.revision_aprobada("Codex Review: Didn't find any major issues. 🎉", 2)
    assert not cadena.revision_aprobada("P1: falta la prueba", 1)


def test_reconoce_la_duda_de_codex():
    texto = "Leí el issue.\nNECESITA-CRITERIO: ¿la visita cuenta si dura menos de 5 minutos? Recomiendo que no.\n"
    assert cadena.pregunta_de_criterio(texto).startswith("¿la visita cuenta")
    assert cadena.pregunta_de_criterio("Listo, subí los cambios.") is None


def test_un_pr_sensible_espera_la_revision_de_opus():
    assert cadena.lista_para_fusionar({"revisado:codex"}, ["gimnasio/socio/rutas.py"])
    assert not cadena.lista_para_fusionar({"revisado:codex"}, ["gimnasio/reglas/motor.py"])
    assert cadena.lista_para_fusionar({"revisado:codex", "revisado:opus"}, ["gimnasio/reglas/motor.py"])
    assert not cadena.lista_para_fusionar({"revisado:opus"}, ["gimnasio/socio/rutas.py"])


def test_un_pr_sin_archivos_nunca_se_fusiona():
    assert not cadena.lista_para_fusionar({"revisado:codex", "revisado:opus"}, [])


def test_el_pedido_de_implementar_incluye_el_issue_y_la_salida_de_criterio():
    texto = cadena.prompt_implementar({"number": 7, "title": "Alta de socio", "body": "Objetivo: X"})
    assert texto.startswith("@codex implementá el issue #7")
    assert "NECESITA-CRITERIO:" in texto
    assert "Objetivo: X" in texto


def test_los_pedidos_de_correccion_llevan_la_marca_que_cuenta_intentos():
    assert cadena.MARCA_CORREGIR in cadena.prompt_corregir("el CI falló.")


def test_un_pr_de_adr_solo_toca_docs_adr_y_glosario():
    assert cadena.es_solo_adr(["docs/adr/0017-tema.md", "GLOSSARY.md"])
    assert not cadena.es_solo_adr(["docs/adr/0017-tema.md", "gimnasio/reglas/progresion.py"])
    assert not cadena.es_solo_adr([])


def test_un_issue_cerrado_pierde_las_etiquetas_de_estado():
    assert cadena.etiquetas_de_estado_a_quitar({"estado:en-curso", "agente:codex", "estado:revision"}) == [
        "estado:en-curso",
        "estado:revision",
    ]
    assert cadena.etiquetas_de_estado_a_quitar({"tipo:funcion", "modulo:visitas"}) == []
