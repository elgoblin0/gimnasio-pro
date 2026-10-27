"""Pruebas de las partes puras del despachador y del resumen del CI (sin gh, git ni agentes)."""

import importlib.util
import os
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


def test_binario_codex_busca_la_app_de_windows_si_no_esta_en_el_path(despachador, tmp_path, monkeypatch):
    monkeypatch.delenv("GIMNASIO_CODEX_BIN", raising=False)
    monkeypatch.setattr(despachador.shutil, "which", lambda _: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert despachador.binario_codex() is None

    bin_ = tmp_path / "OpenAI" / "Codex" / "bin"
    viejo, nuevo = bin_ / "aaa" / "codex.exe", bin_ / "bbb" / "codex.exe"
    for archivo, fecha in ((viejo, 1_000), (nuevo, 2_000)):
        archivo.parent.mkdir(parents=True)
        archivo.write_text("")
        os.utime(archivo, (fecha, fecha))
    assert despachador.binario_codex() == str(nuevo)

    monkeypatch.setenv("GIMNASIO_CODEX_BIN", "C:/elegido/codex.exe")
    assert despachador.binario_codex() == "C:/elegido/codex.exe"


AVISO_LIMITE = (
    '{"type":"error","message":"You\u2019ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), '
    'visit https://chatgpt.com/settings/usage to purchase more credits or try again at 1:06 PM."}'
)


def test_fin_del_limite_lee_la_hora_del_aviso_de_codex(despachador):
    from datetime import datetime

    temprano = datetime(2026, 10, 27, 11, 20)
    assert despachador.fin_del_limite(AVISO_LIMITE, temprano) == datetime(2026, 10, 27, 13, 6)
    # Si la hora ya pasó hoy, es la de mañana.
    assert despachador.fin_del_limite(AVISO_LIMITE, datetime(2026, 10, 27, 14, 0)) == datetime(2026, 10, 28, 13, 6)
    assert despachador.fin_del_limite("hit your usage limit", temprano) == datetime(2026, 10, 27, 11, 50)
    assert despachador.fin_del_limite('{"type":"turn.completed"}', temprano) is None


@pytest.mark.parametrize(
    ("tipo", "agregar", "quitar"),
    [
        ("implementar", ["estado:listo"], ["estado:en-curso", "agente:codex"]),
        ("corregir", ["correccion-pendiente"], ["agente:codex"]),
    ],
)
def test_sin_cupo_el_issue_vuelve_a_la_cola_sin_gastar_un_intento(despachador, monkeypatch, tipo, agregar, quitar):
    from datetime import datetime

    def sin_cupo(_accion):
        raise despachador.LimiteDeUso("codex", datetime(2026, 10, 27, 13, 6))

    etiquetas, comentarios = [], []
    monkeypatch.setattr(despachador, "_ejecutar_accion", sin_cupo)
    monkeypatch.setattr(despachador, "etiquetar", lambda n, a=(), q=(): etiquetas.append((n, a, q)))
    monkeypatch.setattr(despachador, "comentar", lambda n, t: comentarios.append(t))
    issue = despachador.Issue(numero=39, titulo="x", cuerpo="", etiquetas={"ejecutor:codex"})

    with pytest.raises(despachador.LimiteDeUso):
        despachador.ejecutar_accion((tipo, issue, "codex", None))

    assert etiquetas == [(39, agregar, quitar)]
    assert comentarios == []
    assert not despachador.REGISTRO.exists()
