"""Exige subir VERSION en el service worker cuando un PR toca recursos de la PWA.

Sin ese cambio, los navegadores que ya tienen el service worker viejo siguen sirviendo la caché anterior.
Fue el primer hallazgo de la revisión de Codex en #150 y #155; acá lo detecta el CI sin gastar una vuelta.

Uso (en el CI, con el commit de fusión del PR en HEAD y main en HEAD^1):
  python scripts/verificar_cache_pwa.py --base HEAD^1
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SERVICE_WORKER = "gimnasio/static/sw.js"
VERSION = re.compile(r'const VERSION = "(\d+)"')


def toca_recursos_pwa(archivos):
    """Las pruebas JS y el propio service worker no son recursos que el navegador cachee."""
    return any(
        a.startswith("gimnasio/static/") and a != SERVICE_WORKER and not a.endswith(".test.js") for a in archivos
    )


def version_de(codigo):
    encontrada = VERSION.search(codigo or "")
    return int(encontrada[1]) if encontrada else None


def falta_subir_version(archivos, codigo_base, codigo_pr):
    """El motivo del fallo, o None si el PR no toca la PWA o subió VERSION."""
    if not toca_recursos_pwa(archivos):
        return None
    base, nueva = version_de(codigo_base), version_de(codigo_pr)
    if base is None or nueva is None:
        return f"No encontré `const VERSION` en {SERVICE_WORKER}: revisalo a mano."
    if nueva <= base:
        return (
            f"El PR toca recursos de la PWA pero VERSION en {SERVICE_WORKER} sigue en {nueva}: "
            f"subila a {base + 1} para que los navegadores con el service worker viejo reciban el cambio."
        )
    return None


def git(*argumentos):
    return subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8").stdout


def main(argv=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--base", required=True, help="commit de main contra el que se compara")
    args = analizador.parse_args(argv)
    archivos = git("diff", "--name-only", args.base, "HEAD").split()
    motivo = falta_subir_version(
        archivos, git("show", f"{args.base}:{SERVICE_WORKER}"), (RAIZ / SERVICE_WORKER).read_text(encoding="utf-8")
    )
    if motivo:
        print(f"Caché de la PWA: {motivo}")
        return 1
    print("Caché de la PWA: bien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
