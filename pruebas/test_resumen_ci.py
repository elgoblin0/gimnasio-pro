"""Pruebas del resumen del CI (sin gh ni git)."""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar(nombre):
    especificacion = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


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
