"""Hace cumplir las reglas de dependencia del ADR 0001 analizando los import con ast."""

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TRANSVERSALES = {"comun", "reglas", "static"}
PERMITIDOS_EN_REGLAS = {"gimnasio.comun.tipos"}
SQL = {"mysql", "gimnasio.comun.bd"}


def importaciones(archivo, modulo):
    """Devuelve los nombres absolutos que importa un archivo, resolviendo los imports relativos."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    paquete = modulo if archivo.name == "__init__.py" else modulo.rsplit(".", 1)[0]
    nombres = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres += [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            base = nodo.module or ""
            if nodo.level:
                partes = paquete.split(".")
                partes = partes[: len(partes) - nodo.level + 1]
                base = ".".join(partes + ([base] if base else []))
            # Solo el nombre completo: `from gimnasio.comun import tipos` importa gimnasio.comun.tipos.
            nombres += [f"{base}.{alias.name}" for alias in nodo.names]
    return nombres


def es_de(nombre, prefijo):
    return nombre == prefijo or nombre.startswith(prefijo + ".")


def violaciones(raiz, paquete="gimnasio"):
    encontradas = []
    for archivo in sorted((raiz / paquete).rglob("*.py")):
        relativo = archivo.relative_to(raiz).with_suffix("")
        modulo = ".".join(relativo.parts).removesuffix(".__init__")
        partes = modulo.split(".")
        dueno = partes[1] if len(partes) > 1 else None
        for nombre in importaciones(archivo, modulo):
            raiz_import = nombre.split(".")[0]
            propio = es_de(nombre, f"{paquete}.{dueno}") if dueno else False
            if dueno == "reglas" and not propio:
                if raiz_import == paquete:
                    if not any(es_de(nombre, p) for p in PERMITIDOS_EN_REGLAS):
                        encontradas.append(f"{modulo}: reglas/ no puede importar {nombre}")
                elif raiz_import not in sys.stdlib_module_names:
                    encontradas.append(f"{modulo}: reglas/ solo usa la biblioteca estándar, no {nombre}")
            if dueno == "comun" and raiz_import == paquete and not propio:
                encontradas.append(f"{modulo}: comun/ no puede importar el dominio ({nombre})")
            usa_repositorio = "repositorio" in nombre.split(".")
            if raiz_import == paquete and usa_repositorio and not propio:
                encontradas.append(f"{modulo}: usa el repositorio de otro módulo ({nombre}); usá su servicio")
            if partes[-1] == "rutas" and (usa_repositorio or any(es_de(nombre, s) for s in SQL)):
                encontradas.append(f"{modulo}: rutas.py no ejecuta SQL ({nombre})")
    return sorted(set(encontradas))


def test_el_repo_cumple_las_reglas_de_dependencia():
    assert violaciones(RAIZ) == []


def escribir(raiz, ruta, contenido):
    archivo = raiz / ruta
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(contenido, encoding="utf-8")


def test_detecta_cada_regla(tmp_path):
    escribir(tmp_path, "gimnasio/__init__.py", "")
    escribir(tmp_path, "gimnasio/reglas/progresion.py", "import flask\nfrom gimnasio.visitas import servicio\n")
    escribir(
        tmp_path, "gimnasio/reglas/frenos.py", "from datetime import date\nfrom gimnasio.comun.tipos import Razon\n"
    )
    escribir(tmp_path, "gimnasio/comun/reloj.py", "from gimnasio.socios.servicio import algo\n")
    escribir(tmp_path, "gimnasio/visitas/servicio.py", "from gimnasio.socios.repositorio import buscar\n")
    escribir(
        tmp_path, "gimnasio/reglas/sesion.py", "from gimnasio.comun import tipos\nfrom ..comun.tipos import Razon\n"
    )
    escribir(tmp_path, "gimnasio/visitas/rutas.py", "from . import repositorio\nimport mysql.connector\n")
    escribir(tmp_path, "gimnasio/socios/servicio.py", "from .repositorio import buscar\n")
    resultado = "\n".join(violaciones(tmp_path))
    assert "reglas/ solo usa la biblioteca estándar, no flask" in resultado
    assert "reglas/ no puede importar gimnasio.visitas" in resultado
    assert "comun/ no puede importar el dominio" in resultado
    assert "gimnasio.visitas.servicio: usa el repositorio de otro módulo" in resultado
    assert "gimnasio.visitas.rutas: rutas.py no ejecuta SQL (gimnasio.visitas.repositorio)" in resultado
    assert "rutas.py no ejecuta SQL (mysql.connector)" in resultado
    # Lo permitido no aparece: reglas/ con stdlib y comun.tipos, un servicio con su propio repositorio.
    assert "gimnasio.reglas.frenos:" not in resultado
    assert "gimnasio.reglas.sesion:" not in resultado
    assert "gimnasio.socios.servicio:" not in resultado
