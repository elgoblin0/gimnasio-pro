"""Resume los resultados del CI en un markdown corto que los agentes puedan leer sin abrir los logs.

Uso: python scripts/resumen_ci.py <carpeta_artefactos> calidad=success pruebas=failure ...
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_FALLOS = 15
MAX_LINEAS = 40
MARCA = "<!-- resumen-ci -->"


def fallos_de_pytest(carpeta):
    fallos, totales = [], {"pruebas": 0, "fallos": 0, "errores": 0, "saltadas": 0}
    for reporte in carpeta.rglob("reporte-*.xml"):
        raiz = ET.parse(reporte).getroot()
        for suite in raiz.iter("testsuite"):
            totales["pruebas"] += int(suite.get("tests", 0))
            totales["fallos"] += int(suite.get("failures", 0))
            totales["errores"] += int(suite.get("errors", 0))
            totales["saltadas"] += int(suite.get("skipped", 0))
        for caso in raiz.iter("testcase"):
            for problema in list(caso.findall("failure")) + list(caso.findall("error")):
                mensaje = (problema.get("message") or "").strip().splitlines()
                primera = mensaje[0][:200] if mensaje else problema.tag
                fallos.append(f"`{caso.get('classname')}::{caso.get('name')}`: {primera}")
    return totales, fallos


def lineas_de_calidad(carpeta):
    lineas = []
    for archivo in carpeta.rglob("ruff.txt"):
        for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines():
            if linea.strip() and not linea.startswith(("All checks passed", "Found 0")):
                lineas.append(linea)
    return lineas


def main(argumentos):
    carpeta = Path(argumentos[0])
    resultados = dict(par.split("=", 1) for par in argumentos[1:])
    icono = {"success": "✅", "failure": "❌", "cancelled": "⏹️", "skipped": "⏭️"}
    salida = [MARCA, "## Resumen del CI", ""]
    salida.append(" · ".join(f"{icono.get(v, '❔')} {k}" for k, v in resultados.items()))
    totales, fallos = fallos_de_pytest(carpeta)
    if totales["pruebas"]:
        salida += [
            "",
            f"pytest: {totales['pruebas']} pruebas, {totales['fallos']} fallos, "
            f"{totales['errores']} errores, {totales['saltadas']} saltadas.",
        ]
    if fallos:
        salida += ["", "### Fallos de pytest", ""]
        salida += [f"- {fallo}" for fallo in fallos[:MAX_FALLOS]]
        if len(fallos) > MAX_FALLOS:
            salida.append(f"- … y {len(fallos) - MAX_FALLOS} más")
    for trabajo in ("pruebas", "e2e"):
        if resultados.get(trabajo) == "failure" and not fallos_de_pytest(carpeta / trabajo)[1]:
            # Falló antes de producir el reporte (migraciones, importación, Chromium): se muestra el final
            # de los registros de ese trabajo; cada artefacto se descarga en una carpeta con su nombre.
            for registro in sorted((carpeta / trabajo).rglob("registro-*.txt")):
                cola = registro.read_text(encoding="utf-8", errors="replace").splitlines()[-MAX_LINEAS // 2 :]
                salida += ["", f"### {trabajo}/{registro.name}", "", "```", *cola, "```"]
    if resultados.get("calidad") == "failure":
        lineas = lineas_de_calidad(carpeta)
        salida += ["", "### Calidad (ruff, formato, mapa, node)", "", "```"]
        salida += lineas[:MAX_LINEAS]
        if len(lineas) > MAX_LINEAS:
            salida.append(f"… y {len(lineas) - MAX_LINEAS} líneas más")
        salida.append("```")
    if resultados.get("secretos") == "failure":
        salida += ["", "### Secretos", "", "gitleaks encontró posibles secretos: revisá el log del job `secretos`."]
    print("\n".join(salida))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
