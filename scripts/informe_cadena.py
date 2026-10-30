"""Informe de la cadena por etapa: cuánto tardó cada PR de Codex, cuántas vueltas dio y qué encontraron las revisiones.

Reemplaza leer los PR desde Claude para buscar mejoras (lo determinista no gasta cupo). La cadena lo publica en el
issue «Cierre de etapa» cuando se cierra el último issue de Codex de la etapa (ver `cadena.py cierre`).
Un hallazgo de revisión que se repite es candidato a control del CI, como `scripts/verificar_cache_pwa.py`.

Uso:
  python scripts/informe_cadena.py "Etapa 3: Recepción + escena de ocupación"
"""

import re
import sys
from collections import defaultdict

import cadena

MEDIDA = re.compile(r"<!-- implementador:codex minutos=([\d.]+) tokens=(\d+)")
PRIORIDAD = re.compile(r"badge/(P\d)")
FILA_VACIA = {
    "numero": 0,
    "issue": 0,
    "titulo": "",
    "minutos": 0,
    "codex_minutos": 0.0,
    "tokens": 0,
    "correcciones": dict.fromkeys([*cadena.MAX_CORRECCIONES, "sin-origen"], 0),
    "dudas": 0,
    "bloqueado": False,
    "avisos": 0,
    "hallazgos": [],
}


# --- Lógica pura -----------------------------------------------------------


def titulo_de_hallazgo(cuerpo):
    """«P1 Título» de un comentario en línea de Codex (su primera línea, sin la insignia ni el negrito)."""
    primera = (cuerpo or "").strip().splitlines()[0] if (cuerpo or "").strip() else ""
    prioridad = PRIORIDAD.search(primera)
    titulo = re.sub(r"<sub>.*</sub>", "", primera).replace("*", "").strip()
    return f"{prioridad[1]} {titulo}" if prioridad else titulo


def fila(pr, comentarios, hallazgos):
    """Las cifras de un PR fusionado a partir de sus comentarios y los comentarios en línea de Codex."""
    medidas = [MEDIDA.search(c) for c in comentarios]
    correcciones = {origen: cadena.correcciones_pedidas(comentarios, origen) for origen in cadena.MAX_CORRECCIONES}
    pedidas = sum(cadena.MARCA_CORREGIR in c for c in comentarios)
    correcciones["sin-origen"] = pedidas - sum(correcciones.values())
    duracion = cadena.fecha(pr["mergedAt"]) - cadena.fecha(pr["createdAt"])
    return {
        "numero": pr["number"],
        "issue": cadena.numero_de_rama(pr["headRefName"]),
        "titulo": pr["title"],
        "minutos": round(duracion.total_seconds() / 60),
        "codex_minutos": sum(float(m[1]) for m in medidas if m),
        "tokens": sum(int(m[2]) for m in medidas if m),
        "correcciones": correcciones,
        "dudas": sum("duda de criterio" in c.lower() for c in comentarios),
        "bloqueado": any("queda `bloqueado`" in c for c in comentarios),
        "avisos": sum(cadena.MARCA_AVISO in c for c in comentarios),
        "hallazgos": [titulo_de_hallazgo(h) for h in hallazgos],
    }


def sin_prioridad(titulo):
    return re.sub(r"^P\d ", "", titulo)


def informe_markdown(etapa, filas):
    lineas = [
        f"## Informe de la cadena: {etapa}",
        "",
        "| PR | Issue | Minutos | Codex (min / tokens) | Correcciones CI / revisión / Opus / conflicto "
        "| Dudas | Avisos | Bloqueado |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in sorted(filas, key=lambda f: f["numero"]):
        c = f["correcciones"]
        sin_origen = f" (+{c['sin-origen']} sin origen)" if c["sin-origen"] else ""
        lineas.append(
            f"| #{f['numero']} | #{f['issue']} | {f['minutos']} | {f['codex_minutos']:.0f} / {f['tokens']:,} "
            f"| {c['ci']} / {c['revision']} / {c['opus']} / {c['conflicto']}{sin_origen} "
            f"| {f['dudas']} | {f['avisos']} | {'sí' if f['bloqueado'] else ''} |"
        )
    total = sum(f["minutos"] for f in filas)
    lineas += ["", f"{len(filas)} PR, {total} minutos de punta a punta en total.", ""]
    # Codex redacta distinto el mismo hallazgo («…al actualizar recepción», «…para distribuir la conciliación»):
    # se agrupan por las primeras cuatro palabras y se muestra el primer título.
    prs_por_clave, titulo_por_clave = defaultdict(set), {}
    for f in sorted(filas, key=lambda f: f["numero"]):
        for titulo in f["hallazgos"]:
            clave = " ".join(sin_prioridad(titulo).lower().split()[:4])
            prs_por_clave[clave].add(f["numero"])
            titulo_por_clave.setdefault(clave, sin_prioridad(titulo))
    repetidos = sorted((titulo_por_clave[c], prs) for c, prs in prs_por_clave.items() if len(prs) > 1)
    if repetidos:
        lineas += ["### Hallazgos que se repiten (candidatos a control del CI)", ""]
        lineas += [f"- Se repite ({len(prs)} PR): {t}" for t, prs in repetidos]
        lineas.append("")
    hallazgos = [(f["numero"], t) for f in sorted(filas, key=lambda f: f["numero"]) for t in f["hallazgos"]]
    if hallazgos:
        lineas += ["### Hallazgos de las revisiones de Codex", ""]
        lineas += [f"- #{numero}: {titulo}" for numero, titulo in hallazgos]
    return "\n".join(lineas)


# --- GitHub ----------------------------------------------------------------


def informe(etapa):
    """El informe de los PR fusionados de la cadena cuyos issues son de la etapa (milestone) dada."""
    issues = cadena.gh_json(
        "issue", "list", "--milestone", etapa, "--state", "all", "--label", "ejecutor:codex", "--json", "number"
    )
    numeros = {i["number"] for i in issues}
    prs = cadena.gh_json(
        "pr",
        "list",
        "--state",
        "merged",
        "--limit",
        "200",
        "--json",
        "number,title,headRefName,createdAt,mergedAt,comments",
    )
    filas = []
    for pr in prs:
        if cadena.numero_de_rama(pr["headRefName"]) not in numeros:
            continue
        en_linea = cadena.gh_json("api", f"repos/{cadena.repo()}/pulls/{pr['number']}/comments?per_page=100")
        hallazgos = [c["body"] for c in en_linea if c["user"]["login"] == cadena.BOT_CODEX]
        filas.append(fila(pr, [c["body"] for c in pr["comments"]], hallazgos))
    return informe_markdown(etapa, filas)


def main(argv=None):
    argumentos = sys.argv[1:] if argv is None else argv
    if len(argumentos) != 1:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # la consola de Windows usa cp1252
    print(informe(argumentos[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
