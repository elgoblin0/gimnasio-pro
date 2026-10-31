"""Controles mecánicos sobre el diff de un PR: lo que la revisión de Codex encontraba y un script puede detectar.

- Versión del motor (#135): cambiar un módulo de `reglas/` que registra VERSION_REGLAS exige subirla.
- Hechos en migraciones (#191): alterar una tabla de hechos exige la línea `-- Autoriza Opus: #N` en la migración.
- Ficha de capacidad (#172): una prueba e2e nueva exige tocar `docs/capacidades/`, o `# Sin ficha: <motivo>` en ella.

La caché de la PWA tiene su propio control: `scripts/verificar_cache_pwa.py`.

Uso (en el CI, con el commit de fusión del PR en HEAD y main en HEAD^1):
  python scripts/verificar_pr.py --base HEAD^1
"""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_VERSION = "gimnasio/reglas/version.py"
VERSION = re.compile(r'VERSION_REGLAS = "(\d+)\.(\d+)\.(\d+)"')
HECHOS = {
    "pagos",
    "cambios_sede",
    "borrados_salud",
    "revisiones_aviso",
    "cambios_estado_equipo",
    "restricciones_salud",
    "dolores_reportados",
    "chequeos_dia",
    "avisos_entrenador",
    "prescripciones_efectivas",
    "consentimientos",
    "entradas",
    "salidas",
    "sesiones_realizadas",
    "series_realizadas",
    "sustituciones",
}
AUTORIZACION = re.compile(r"^-- Autoriza Opus: #\d+", re.M)
COMENTARIOS_Y_VALORES = re.compile(r"--[^\n]*|\#[^\n]*|/\*.*?\*/|'(?:''|\\.|[^'])*'", re.S)
ESCRITURA = re.compile(
    r"\b(?:ALTER\s+TABLE|DROP\s+TABLE(?:\s+IF\s+EXISTS)?|TRUNCATE(?:\s+TABLE)?|RENAME\s+TABLE|UPDATE|DELETE\s+FROM)"
    r"\s+(?:`?\w+`?\.)?`?(\w+)`?",
    re.I,
)
SIN_FICHA = re.compile(r"^# Sin ficha: \S", re.M)


def estructura(codigo):
    """El árbol sin comentarios, formato ni docstrings: documentar no cambia el motor."""
    try:
        arbol = ast.parse(codigo)
    except SyntaxError:
        return codigo
    for nodo in ast.walk(arbol):
        documentable = isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        if documentable and ast.get_docstring(nodo, clean=False) is not None:
            nodo.body = nodo.body[1:]
    return ast.dump(arbol)


def version_de(codigo):
    encontrada = VERSION.search(codigo or "")
    return tuple(int(parte) for parte in encontrada.groups()) if encontrada else None


def falta_subir_motor(archivos, leer_base, leer_pr):
    """El motivo del fallo, o None. Solo cuentan los módulos cuyas decisiones quedan guardadas con VERSION_REGLAS."""
    cambiados = []
    for archivo in archivos:
        if not archivo.startswith("gimnasio/reglas/") or not archivo.endswith(".py") or archivo == ARCHIVO_VERSION:
            continue
        base, nuevo = leer_base(archivo) or "", leer_pr(archivo) or ""
        if "VERSION_REGLAS" in base + nuevo and estructura(base) != estructura(nuevo):
            cambiados.append(archivo)
    if not cambiados:
        return None
    base, nueva = version_de(leer_base(ARCHIVO_VERSION)), version_de(leer_pr(ARCHIVO_VERSION))
    if base is None or nueva is None:
        return f"No encontré VERSION_REGLAS en {ARCHIVO_VERSION}: revisalo a mano."
    if nueva <= base:
        return (
            f"{', '.join(cambiados)} cambia el motor pero VERSION_REGLAS sigue en {'.'.join(map(str, nueva))}: "
            f"subila en {ARCHIVO_VERSION} para distinguir lo guardado antes y después."
        )
    return None


def hechos_alterados(sql):
    """Las tablas de hechos que la migración modifica, sin mirar comentarios ni valores."""
    limpio = COMENTARIOS_Y_VALORES.sub(" ", sql)
    return sorted({tabla.lower() for tabla in ESCRITURA.findall(limpio)} & HECHOS)


def falta_autorizar_hechos(archivos, leer_pr):
    """El motivo del fallo, o None. Opus revisa el diff de toda migración y ve la línea de autorización."""
    motivos = []
    for archivo in archivos:
        ruta = PurePosixPath(archivo)
        sql = leer_pr(archivo) if ruta.parent.name == "migraciones" and ruta.suffix == ".sql" else None
        if not sql or AUTORIZACION.search(sql):
            continue
        tablas = hechos_alterados(sql)
        if tablas:
            motivos.append(
                f"{archivo} altera tablas de hechos ({', '.join(tablas)}): "
                "solo Opus las autoriza (ADR 0003), con la línea `-- Autoriza Opus: #N`. Si sos Codex, "
                "etiquetá `necesita-criterio`."
            )
    return "\n".join(motivos) or None


def falta_ficha(archivos, agregados, leer_pr):
    """El motivo del fallo, o None. Aproxima «cambió una capacidad»: una prueba e2e nueva es la señal mecánica."""
    if any(archivo.startswith("docs/capacidades/") for archivo in archivos):
        return None
    motivos = []
    for archivo in agregados:
        ruta = PurePosixPath(archivo)
        es_e2e = ruta.parent.as_posix() == "pruebas/e2e" and ruta.name.startswith("test_") and ruta.suffix == ".py"
        if es_e2e and not SIN_FICHA.search(leer_pr(archivo) or ""):
            motivos.append(
                f"{archivo} es una prueba e2e nueva y el PR no toca docs/capacidades/: editá la ficha y regenerá "
                "el mapa, o, si no cambia ninguna capacidad, agregá `# Sin ficha: <motivo>` a la prueba."
            )
    return "\n".join(motivos) or None


def git(*argumentos):
    resultado = subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    return resultado.stdout if resultado.returncode == 0 else None


def leer_disco(archivo):
    ruta = RAIZ / archivo
    return ruta.read_text(encoding="utf-8") if ruta.is_file() else None


def main(argv=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--base", required=True, help="commit de main contra el que se compara")
    args = analizador.parse_args(argv)
    archivos = (git("diff", "--name-only", args.base, "HEAD") or "").splitlines()
    agregados = (git("diff", "--name-only", "--diff-filter=A", args.base, "HEAD") or "").splitlines()
    motivos = [
        falta_subir_motor(archivos, lambda archivo: git("show", f"{args.base}:{archivo}"), leer_disco),
        falta_autorizar_hechos(archivos, leer_disco),
        falta_ficha(archivos, agregados, leer_disco),
    ]
    motivos = [motivo for motivo in motivos if motivo]
    if motivos:
        print("\n".join(motivos))
        return 1
    print("Controles del PR: bien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
