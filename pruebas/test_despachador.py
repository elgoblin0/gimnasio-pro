"""Pruebas de las partes puras del despachador y del resumen del CI (sin gh, git ni agentes)."""

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def cargar(nombre):
    especificacion = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def despachador(tmp_path, monkeypatch):
    modulo = cargar("despachador")
    monkeypatch.setattr(modulo, "REGISTRO", tmp_path / "registro.jsonl")
    monkeypatch.setattr(modulo, "CANDADO", tmp_path / "corriendo.lock")
    return modulo


def revision(pr, **campos):
    return {"fase": "revisar", "pr": pr, "ejecutor": "codex", "fallida": False, **campos}


def test_aprueba_si_solo_hay_hallazgos_menores(despachador):
    menor = {"archivo": "a.py", "problema": "x", "gravedad": "menor"}
    bloqueante = {**menor, "gravedad": "bloqueante"}
    assert despachador.aprobado([])
    assert despachador.aprobado([menor])
    assert not despachador.aprobado([menor, bloqueante])


def test_leer_hallazgos_rechaza_salidas_que_no_son_el_json_pedido(despachador):
    assert despachador.leer_hallazgos('{"hallazgos": []}') == []
    assert despachador.leer_hallazgos("tiempo agotado") is None
    assert despachador.leer_hallazgos('{"aprobado": true}') is None


def test_ultima_revision_toma_la_ultima_con_veredicto_del_mismo_pr_y_revisor(despachador):
    hallazgos = [{"archivo": "a.py", "problema": "x", "gravedad": "bloqueante"}]
    for entrada in [
        revision(12, commit="aaa", hallazgos=hallazgos),
        revision(12, commit="bbb", hallazgos=[], ejecutor="opus"),
        revision(11, commit="ccc", hallazgos=[]),
        revision(12, commit="ddd", hallazgos=None, fallida=True),
    ]:
        despachador.registrar(entrada)
    anterior = despachador.ultima_revision(12, "codex")
    assert anterior["commit"] == "aaa"
    assert anterior["hallazgos"] == hallazgos


def test_ultima_revision_ignora_las_revisiones_anteriores_al_formato_incremental(despachador):
    despachador.registrar(revision(12))
    assert despachador.ultima_revision(12, "codex") is None


def test_la_segunda_ronda_lleva_los_hallazgos_anteriores_y_solo_el_diff_nuevo(despachador):
    issue = despachador.Issue(numero=7, titulo="Dos direcciones", cuerpo="Cuerpo", etiquetas=set())
    hallazgos = [{"archivo": "estilos.css", "problema": "contraste bajo", "gravedad": "bloqueante"}]
    prompt = despachador.prompt_revisar_de_nuevo(issue, "+nuevo", hallazgos, "(sin resumen)", sensible=False)
    assert "**bloqueante** `estilos.css`: contraste bajo" in prompt
    assert "# Diff desde la revisión anterior" in prompt
    assert "+nuevo" in prompt


def test_un_segundo_despachador_no_toma_el_candado(despachador):
    primero = despachador.tomar_candado_instancia()
    assert primero is not None
    try:
        assert despachador.tomar_candado_instancia() is None
    finally:
        primero.close()
    segundo = despachador.tomar_candado_instancia()
    assert segundo is not None
    segundo.close()


def test_el_resumen_del_ci_muestra_el_e2e_y_su_registro_si_falla(tmp_path, capsys):
    (tmp_path / "e2e").mkdir()
    (tmp_path / "e2e" / "registro-pytest.txt").write_text("Chromium no arrancó\n", encoding="utf-8")
    cargar("resumen_ci").main([str(tmp_path), "calidad=success", "pruebas=success", "e2e=failure"])
    salida = capsys.readouterr().out
    assert "❌ e2e" in salida
    assert "### e2e/registro-pytest.txt" in salida
    assert "Chromium no arrancó" in salida


def test_el_resumen_no_repite_registros_de_un_trabajo_que_paso(tmp_path, capsys):
    for trabajo in ("pruebas", "e2e"):
        (tmp_path / trabajo).mkdir()
        (tmp_path / trabajo / "registro-pytest.txt").write_text(f"log de {trabajo}\n", encoding="utf-8")
    cargar("resumen_ci").main([str(tmp_path), "pruebas=failure", "e2e=success"])
    salida = capsys.readouterr().out
    assert "log de pruebas" in salida
    assert "log de e2e" not in salida
