"""Encadena el trabajo entre Codex cloud, Opus y la fusión, usando GitHub como buzón.

Corre en GitHub Actions (.github/workflows/cadena.yml) con el token personal del dueño en GH_TOKEN:
los eventos que genera el GITHUB_TOKEN no disparan otros workflows, y Codex solo responde a
menciones de una cuenta vinculada. Ver docs/protocolo-agentes.md.

Uso:
  python scripts/cadena.py arrancar
  python scripts/cadena.py tras-ci --rama codex/issue-12 --resultado success
  python scripts/cadena.py revision --pr 40 --texto-archivo cuerpo.txt [--revision 123]
  python scripts/cadena.py etiqueta --pr 40 --etiqueta revisado:codex
  python scripts/cadena.py fusionar-adr --rama opus/adr-0017-tema
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PREFIJO_RAMA = "codex/issue-"
BOT_CODEX = "chatgpt-codex-connector[bot]"
RUTAS_SENSIBLES = (
    "gimnasio/reglas/",
    "migraciones/",
    "gimnasio/comun/migrar.py",
    "gimnasio/permisos/",
    "gimnasio/salud/",
)
PREFIJO_ADR = "opus/adr-"
RUTAS_ADR = ("docs/adr/", "GLOSSARY.md")
MAX_CORRECCIONES = 3
MARCA_CORREGIR = "<!-- cadena:corregir -->"
MARCA_REVISAR = "<!-- cadena:revisar {sha} -->"
APROBACION_CODEX = "didn't find any major issues"
PEDIDO_CRITERIO = "NECESITA-CRITERIO:"


# --- Lógica pura -----------------------------------------------------------


def dependencias(cuerpo):
    linea = re.search(r"Depende de:\s*(.*)", cuerpo or "")
    return [int(n) for n in re.findall(r"#(\d+)", linea.group(1))] if linea else []


def elegir_siguiente(issues, esta_cerrado):
    """El issue listo de número más bajo cuyas dependencias están todas cerradas."""
    for issue in sorted(issues, key=lambda i: i["number"]):
        if all(esta_cerrado(n) for n in dependencias(issue["body"])):
            return issue
    return None


def numero_de_rama(rama):
    return int(rama.removeprefix(PREFIJO_RAMA)) if rama.startswith(PREFIJO_RAMA) else None


def es_sensible(archivos):
    return any(a.startswith(RUTAS_SENSIBLES) for a in archivos)


def revision_aprobada(texto, comentarios_en_linea):
    return comentarios_en_linea == 0 or APROBACION_CODEX in (texto or "").lower()


def pregunta_de_criterio(texto):
    for linea in (texto or "").splitlines():
        if linea.strip().startswith(PEDIDO_CRITERIO):
            return linea.strip().removeprefix(PEDIDO_CRITERIO).strip()
    return None


def es_solo_adr(archivos):
    """Un PR de ADR provisional toca únicamente docs/adr/ y el glosario."""
    return bool(archivos) and all(a.startswith(RUTAS_ADR) for a in archivos)


def lista_para_fusionar(etiquetas, archivos):
    """Un PR sin archivos nunca se fusiona: cerraría su issue sin implementarlo (#127)."""
    sensible = es_sensible(archivos)
    return bool(archivos) and "revisado:codex" in etiquetas and (not sensible or "revisado:opus" in etiquetas)


def prompt_implementar(issue):
    return (
        f"@codex implementá el issue #{issue['number']} en esta rama, según AGENTS.md y "
        "docs/protocolo-agentes.md. Corré ruff y pytest antes de subir.\n"
        f"Si te falta una decisión de diseño, producto, alcance o término, no implementes: respondé "
        f"con una sola línea que empiece con `{PEDIDO_CRITERIO}` y la duda con tu recomendación.\n\n"
        f"## {issue['title']}\n\n{issue['body']}"
    )


def prompt_corregir(motivo):
    return f"{MARCA_CORREGIR}\n@codex {motivo} Subí la corrección a esta rama sin salirte del alcance del issue."


# --- GitHub ----------------------------------------------------------------


def gh(*argumentos):
    resultado = subprocess.run(["gh", *argumentos], capture_output=True, text=True, encoding="utf-8")
    if resultado.returncode != 0:
        raise RuntimeError(f"gh {' '.join(argumentos)}: {resultado.stderr.strip()}")
    return resultado.stdout


def gh_json(*argumentos):
    return json.loads(gh(*argumentos) or "null")


def repo():
    return os.environ["GITHUB_REPOSITORY"]


def esta_cerrado(numero):
    return gh_json("issue", "view", str(numero), "--json", "state")["state"] == "CLOSED"


def prs_de_codex():
    prs = gh_json("pr", "list", "--state", "open", "--json", "number,title,headRefName,labels,body", "--limit", "100")
    return [p for p in prs if p["headRefName"].startswith(PREFIJO_RAMA)]


def etiquetas_de(pr):
    return {e["name"] for e in pr["labels"]}


def archivos_del_pr(numero):
    return [a["path"] for a in gh_json("pr", "view", str(numero), "--json", "files")["files"]]


def comentarios_del_pr(numero):
    return [c["body"] for c in gh_json("pr", "view", str(numero), "--json", "comments")["comments"]]


def comentar(numero, texto):
    gh("pr", "comment", str(numero), "--body", texto)


def etiquetar(numero, agregar=(), quitar=(), tipo="pr"):
    argumentos = [tipo, "edit", str(numero)]
    for etiqueta in agregar:
        argumentos += ["--add-label", etiqueta]
    for etiqueta in quitar:
        argumentos += ["--remove-label", etiqueta]
    if len(argumentos) > 3:
        gh(*argumentos)


def crear_rama_vacia(rama):
    """Rama desde main con un commit vacío, para poder abrir el PR borrador antes de que Codex trabaje."""
    base = gh_json("api", f"repos/{repo()}/git/ref/heads/main")["object"]["sha"]
    arbol = gh_json("api", f"repos/{repo()}/git/commits/{base}")["tree"]["sha"]
    commit = gh_json(
        "api",
        f"repos/{repo()}/git/commits",
        "-f",
        f"message=Inicia {rama}",
        "-f",
        f"tree={arbol}",
        "-f",
        f"parents[]={base}",
    )["sha"]
    gh("api", f"repos/{repo()}/git/refs", "-f", f"ref=refs/heads/{rama}", "-f", f"sha={commit}")


def pedir_correccion(numero, motivo):
    """Le pide a Codex que corrija, con un tope de intentos por PR."""
    intentos = sum(MARCA_CORREGIR in c for c in comentarios_del_pr(numero))
    if intentos >= MAX_CORRECCIONES:
        etiquetar(numero, agregar=["bloqueado"])
        comentar(numero, f"Codex agotó {MAX_CORRECCIONES} correcciones: queda `bloqueado` para el dueño.")
        return
    comentar(numero, prompt_corregir(motivo))


# --- Pasos -----------------------------------------------------------------


def arrancar():
    """Lanza el siguiente issue listo, o reanuda el PR en curso si Opus resolvió su duda."""
    for pr in prs_de_codex():
        numero_issue = numero_de_rama(pr["headRefName"])
        issue = gh_json("issue", "view", str(numero_issue), "--json", "number,title,body,labels")
        if "estado:listo" in etiquetas_de(issue):
            etiquetar(numero_issue, agregar=["estado:en-curso", "agente:codex"], quitar=["estado:listo"], tipo="issue")
            comentar(
                pr["number"],
                "@codex Opus resolvió la duda en el issue: leé su comentario y seguí.\n\n" + prompt_implementar(issue),
            )
            print(f"Reanudado el PR #{pr['number']}.")
        else:
            print(f"Ya hay un issue en curso (PR #{pr['number']}): un issue a la vez.")
        return
    listos = gh_json(
        "issue",
        "list",
        "--state",
        "open",
        "--label",
        "estado:listo",
        "--label",
        "ejecutor:codex",
        "--json",
        "number,title,body",
        "--limit",
        "100",
    )
    issue = elegir_siguiente(listos, esta_cerrado)
    if issue is None:
        print("No hay issues listos con las dependencias cerradas.")
        return
    rama = f"{PREFIJO_RAMA}{issue['number']}"
    crear_rama_vacia(rama)
    url = gh(
        "pr",
        "create",
        "--draft",
        "--base",
        "main",
        "--head",
        rama,
        "--title",
        issue["title"],
        "--body",
        f"Closes #{issue['number']}\n\nPR abierto por la cadena (scripts/cadena.py); lo implementa Codex cloud.",
    ).strip()
    etiquetar(issue["number"], agregar=["estado:en-curso", "agente:codex"], quitar=["estado:listo"], tipo="issue")
    comentar(url.rsplit("/", 1)[-1], prompt_implementar(issue))
    print(f"Lanzado el issue #{issue['number']}: {url}")


def tras_ci(rama, resultado):
    """CI verde con cambios: pide la revisión de Codex. CI rojo: pide la corrección."""
    if numero_de_rama(rama) is None or resultado not in ("success", "failure"):
        return
    pr = next((p for p in prs_de_codex() if p["headRefName"] == rama), None)
    if pr is None or not archivos_del_pr(pr["number"]):
        return
    numero = pr["number"]
    if resultado == "failure":
        pedir_correccion(numero, "el CI falló: leé el resumen del CI en este PR y arreglalo.")
        return
    sha = gh_json("pr", "view", str(numero), "--json", "headRefOid")["headRefOid"]
    marca = MARCA_REVISAR.format(sha=sha)
    if any(marca in c for c in comentarios_del_pr(numero)):
        return
    etiquetar(numero, agregar=["estado:revision"], quitar=["revisado:codex", "revisado:opus", "correccion-pendiente"])
    gh("pr", "ready", str(numero))
    comentar(numero, f"{marca}\n@codex review")


def revision(numero, texto, id_revision=None):
    """Interpreta lo que respondió Codex en el PR: una duda, una aprobación o hallazgos."""
    pr = next((p for p in prs_de_codex() if p["number"] == numero), None)
    if pr is None:
        return
    pregunta = pregunta_de_criterio(texto)
    if pregunta:
        numero_issue = numero_de_rama(pr["headRefName"])
        gh("issue", "comment", str(numero_issue), "--body", f"Duda de Codex (PR #{numero}):\n\n> {pregunta}")
        etiquetar(numero_issue, agregar=["necesita-criterio"], quitar=["estado:en-curso", "agente:codex"], tipo="issue")
        return
    if id_revision is None:
        if APROBACION_CODEX in (texto or "").lower():
            etiquetar(numero, agregar=["revisado:codex"])
        return
    en_linea = len(gh_json("api", f"repos/{repo()}/pulls/{numero}/reviews/{id_revision}/comments"))
    if revision_aprobada(texto, en_linea):
        etiquetar(numero, agregar=["revisado:codex"], quitar=["correccion-pendiente"])
    else:
        etiquetar(numero, agregar=["correccion-pendiente"])
        pedir_correccion(numero, "corregí los hallazgos de tu revisión.")


def etiqueta(numero, nombre):
    """Reacciona a una etiqueta nueva en un PR de Codex: fusionar o corregir lo que pidió Opus."""
    pr = next((p for p in prs_de_codex() if p["number"] == numero), None)
    if pr is None or "bloqueado" in etiquetas_de(pr):
        return
    if nombre == "correccion-pendiente" and "revisado:codex" in etiquetas_de(pr):
        pedir_correccion(numero, "atendé la revisión de Opus que está en este PR.")
        return
    if lista_para_fusionar(etiquetas_de(pr), archivos_del_pr(numero)):
        # Una revisión pedida a mano puede llegar con el PR aún en borrador; GitHub no fusiona borradores.
        gh("pr", "ready", str(numero))
        gh("pr", "merge", str(numero), "--squash", "--auto", "--delete-branch")
        print(f"Fusión automática activada en el PR #{numero}.")


def fusionar_adr(rama):
    """Activa la fusión automática de un ADR provisional de Opus; el ruleset espera los checks requeridos."""
    pr = next((p for p in gh_json("pr", "list", "--state", "open", "--head", rama, "--json", "number,labels")), None)
    if pr is None or "bloqueado" in etiquetas_de(pr):
        return
    if not es_solo_adr(archivos_del_pr(pr["number"])):
        print(f"El PR #{pr['number']} toca algo más que ADR y glosario: no se fusiona solo.")
        return
    gh("pr", "merge", str(pr["number"]), "--squash", "--auto", "--delete-branch")
    print(f"Fusión automática activada en el ADR #{pr['number']}.")


def main(argv=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    pasos = analizador.add_subparsers(dest="paso", required=True)
    pasos.add_parser("arrancar")
    pasos.add_parser("fusionar-adr").add_argument("--rama", required=True)
    p = pasos.add_parser("tras-ci")
    p.add_argument("--rama", required=True)
    p.add_argument("--resultado", required=True)
    p = pasos.add_parser("revision")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--texto-archivo", type=Path, required=True)
    p.add_argument("--revision", type=int)
    p = pasos.add_parser("etiqueta")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--etiqueta", required=True)
    args = analizador.parse_args(argv)
    if args.paso == "arrancar":
        arrancar()
    elif args.paso == "tras-ci":
        tras_ci(args.rama, args.resultado)
    elif args.paso == "revision":
        revision(args.pr, args.texto_archivo.read_text(encoding="utf-8"), args.revision)
    elif args.paso == "fusionar-adr":
        fusionar_adr(args.rama)
    else:
        etiqueta(args.pr, args.etiqueta)


if __name__ == "__main__":
    sys.exit(main())
