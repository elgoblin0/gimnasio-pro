"""Detecta accesos al reloj del sistema fuera del módulo autorizado."""

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PROHIBIDAS = {"datetime.datetime.now", "datetime.datetime.utcnow", "datetime.date.today", "time.time"}


def _nombres(nodo, alias):
    if isinstance(nodo, ast.Name):
        return alias.get(nodo.id, {nodo.id})
    if isinstance(nodo, ast.Attribute):
        return {f"{nombre}.{nodo.attr}" for nombre in _nombres(nodo.value, alias)}
    return set()


def violaciones(raiz):
    encontradas = []
    for archivo in sorted((raiz / "gimnasio").rglob("*.py")):
        relativo = archivo.relative_to(raiz).as_posix()
        if relativo == "gimnasio/comun/reloj.py":
            continue
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        # Conservamos todas las resoluciones: un import local no debe ocultar
        # llamadas prohibidas en otros ámbitos del mismo archivo.
        alias = {"datetime": {"datetime.datetime"}, "date": {"datetime.date"}, "time": {"time"}}
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for nombre in nodo.names:
                    alias.setdefault(nombre.asname or nombre.name.split(".")[0], set()).add(nombre.name)
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                for nombre in nodo.names:
                    alias.setdefault(nombre.asname or nombre.name, set()).add(f"{nodo.module}.{nombre.name}")
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                for nombre in sorted(_nombres(nodo.func, alias) & PROHIBIDAS):
                    encontradas.append(f"{relativo}:{nodo.lineno}: llamada prohibida a {nombre}")
    return encontradas


def test_el_repo_no_usa_el_reloj_del_sistema_fuera_de_reloj():
    assert violaciones(RAIZ) == []


@pytest.mark.parametrize(
    "codigo",
    [
        "from datetime import datetime\ndatetime.now()",
        "from datetime import datetime\ndatetime.utcnow()",
        "from datetime import date\ndate.today()",
        "import time\ntime.time()",
        "import datetime as fechas\nfechas.datetime.now()",
        "from datetime import datetime as momento\nmomento.utcnow()",
        "from datetime import date as fecha\nfecha.today()",
        "from time import time as segundos\nsegundos()",
        "from datetime import datetime\ndatetime.now (\n)",
    ],
)
def test_detecta_llamadas_prohibidas_en_un_archivo_temporal(tmp_path, codigo):
    carpeta = tmp_path / "gimnasio" / "sistema"
    carpeta.mkdir(parents=True)
    (carpeta / "servicio.py").write_text(codigo, encoding="utf-8")
    resultado = violaciones(tmp_path)
    assert len(resultado) == 1
    assert resultado[0].startswith("gimnasio/sistema/servicio.py:2: llamada prohibida")


@pytest.mark.parametrize(
    "codigo",
    [
        "from datetime import datetime\n"
        "def ahora():\n    return datetime.now()\n"
        "def construir():\n    import datetime\n    return datetime.datetime(2026, 1, 1)\n",
        "import datetime\n"
        "def ahora():\n    return datetime.datetime.now()\n"
        "def construir():\n    from datetime import datetime\n    return datetime(2026, 1, 1)\n",
    ],
)
def test_un_import_local_no_oculta_llamadas_en_otro_ambito(tmp_path, codigo):
    carpeta = tmp_path / "gimnasio"
    carpeta.mkdir()
    (carpeta / "servicio.py").write_text(codigo, encoding="utf-8")
    resultado = violaciones(tmp_path)
    assert resultado == ["gimnasio/servicio.py:3: llamada prohibida a datetime.datetime.now"]


def test_exime_solo_reloj_y_scripts_e_ignora_comentarios_y_textos(tmp_path):
    comun = tmp_path / "gimnasio" / "comun"
    comun.mkdir(parents=True)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    codigo = "from datetime import datetime\ndatetime.now()"
    (comun / "reloj.py").write_text(codigo, encoding="utf-8")
    (scripts / "tarea.py").write_text(codigo, encoding="utf-8")
    (comun / "texto.py").write_text('# datetime.now()\ntexto = "time.time()"\n', encoding="utf-8")
    assert violaciones(tmp_path) == []
    otra_carpeta = tmp_path / "gimnasio" / "sistema"
    otra_carpeta.mkdir()
    (otra_carpeta / "reloj.py").write_text(codigo, encoding="utf-8")
    assert len(violaciones(tmp_path)) == 1
