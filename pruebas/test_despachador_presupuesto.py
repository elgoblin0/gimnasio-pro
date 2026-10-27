"""Pruebas del presupuesto de Opus del despachador (ADR 0011), sin gh, git ni agentes."""

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DESDE = datetime(2026, 10, 26, 3, tzinfo=UTC)


@pytest.fixture
def despachador(tmp_path, monkeypatch):
    especificacion = importlib.util.spec_from_file_location("despachador", RAIZ / "scripts" / "despachador.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    monkeypatch.setattr(modulo, "RAIZ", Path("C:/proyectos/gimnasio-pro"))
    monkeypatch.setattr(modulo, "REGISTRO", tmp_path / "registro.jsonl")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    return modulo


def mensaje(id_, fecha, salida=1000, lectura=0, tipo="assistant"):
    uso = {"input_tokens": 0, "output_tokens": salida, "cache_read_input_tokens": lectura}
    return {"type": tipo, "timestamp": fecha, "message": {"id": id_, "usage": uso}}


def sesion(tmp_path, proyecto, eventos, nombre="sesion.jsonl"):
    carpeta = tmp_path / "claude" / "projects" / proyecto
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text("\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8")


def test_cuenta_las_sesiones_del_repo_y_sus_worktrees_una_vez_por_mensaje(despachador, tmp_path):
    sesion(
        tmp_path,
        "C--proyectos-gimnasio-pro",
        [
            mensaje("a", "2026-10-26T10:00:00Z", salida=1000, lectura=10_000),
            mensaje("a", "2026-10-26T10:00:00Z", salida=1000, lectura=10_000),  # otro bloque del mismo mensaje
            mensaje("b", "2026-10-25T10:00:00Z", salida=5000),  # de la semana anterior
            mensaje("c", "2026-10-26T11:00:00Z", tipo="user"),
        ],
    )
    sesion(tmp_path, "C--proyectos-gimnasio-pro-trabajo-issue-5", [mensaje("d", "2026-10-27T01:00:00Z", salida=500)])
    sesion(tmp_path, "C--proyectos-otro-repo", [mensaje("e", "2026-10-27T01:00:00Z", salida=9000)])
    assert despachador.consumo_interactivo(DESDE) == 1000 + 0.1 * 10_000 + 500


def test_sin_carpeta_de_sesiones_no_suma_nada(despachador):
    assert despachador.consumo_interactivo(DESDE) == 0


def test_el_consumo_semanal_de_opus_suma_registro_y_sesiones(despachador, tmp_path, monkeypatch):
    monkeypatch.setattr(despachador, "inicio_de_semana", lambda: DESDE)
    despachador.registrar({"ejecutor": "opus", "fase": "implementar", "ponderados": 300})
    despachador.registrar({"ejecutor": "codex", "fase": "implementar", "ponderados": 7000})
    sesion(tmp_path, "C--proyectos-gimnasio-pro", [mensaje("a", "2026-10-26T10:00:00Z", salida=200)])
    assert despachador.consumo_semanal("opus") == 500
    assert despachador.consumo_semanal("codex") == 7000


def test_no_corre_hasta_vaciar_dentro_de_una_sesion_de_claude(despachador, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr("sys.argv", ["despachador.py", "--hasta-vaciar"])
    # Sin esto, si la protección falta, la prueba lanzaría el despachador real contra GitHub.
    monkeypatch.setattr(despachador, "ciclo", lambda _: pytest.fail("arrancó el ciclo dentro de Claude"))
    assert despachador.main() == 2
    assert "terminal aparte" in capsys.readouterr().err
