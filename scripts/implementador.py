"""Implementador local: hace en esta PC lo que Codex cloud no responde desde GitHub (ver docs/protocolo-agentes.md).

La cadena (scripts/cadena.py) sigue abriendo el PR borrador y comentando `@codex implementá…` o
`@codex corregí…`. Este script toma el último pedido de esos comentarios que nadie atendió, corre `codex exec`
en un worktree de la rama del PR, sube el resultado y deja un comentario con la marca de «hecho». El CI, la
revisión y la fusión siguen a cargo de la cadena.

Uso:
  python scripts/implementador.py            # atiende los pedidos pendientes y termina
  python scripts/implementador.py --esperar  # repite cada 60 segundos hasta Ctrl+C
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cadena

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_TRABAJO = RAIZ / ".implementador"
MARCA_HECHO = "<!-- implementador:hecho -->"
MARCA_FALLO = "<!-- implementador:fallo -->"
MAX_FALLOS = 2
LIMITE_MINUTOS = 60
ESPERA_SEGUNDOS = 60
PEDIDO = re.compile(r"^\s*@codex\s+(?!review\b)\S", re.IGNORECASE)


# --- Lógica pura -----------------------------------------------------------


def es_pedido(cuerpo):
    """Un comentario de la cadena que le pide trabajo a Codex (no la revisión, que sí responde en la nube)."""
    return bool(PEDIDO.match(re.sub(r"<!--.*?-->", "", cuerpo or "", flags=re.DOTALL)))


def pedido_pendiente(comentarios):
    """El último pedido sin atender, o None.

    Un comentario con la marca de hecho cierra todo lo anterior; cada marca de fallo cuenta para el tope
    de intentos del pedido vigente.
    """
    pendiente, fallos = None, 0
    for cuerpo in comentarios:
        if MARCA_HECHO in cuerpo:
            pendiente, fallos = None, 0
        elif MARCA_FALLO in cuerpo:
            fallos += 1
        elif es_pedido(cuerpo):
            pendiente, fallos = cuerpo, 0
    return pendiente, fallos


def prompt_para_codex(pedido):
    texto = re.sub(r"<!--.*?-->", "", pedido, flags=re.DOTALL).strip().removeprefix("@codex").strip()
    return (
        "Trabajás en un worktree de la rama de este PR. No hagas commit ni push: lo hace el implementador.\n"
        "Si la rama tiene conflictos con main sin resolver, resolvelos preservando el alcance del issue.\n\n" + texto
    )


# --- Codex y git -----------------------------------------------------------


def binario_codex():
    """El ejecutable de Codex, o None. La app de Windows no lo agrega al PATH y el hash de su carpeta cambia."""
    if os.environ.get("GIMNASIO_CODEX_BIN"):
        return os.environ["GIMNASIO_CODEX_BIN"]
    if encontrado := shutil.which("codex"):
        return encontrado
    local = os.environ.get("LOCALAPPDATA")
    instalados = list((Path(local) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe")) if local else []
    return str(max(instalados, key=lambda p: p.stat().st_mtime)) if instalados else None


def git(*argumentos, cwd=RAIZ, chequear=True):
    resultado = subprocess.run(
        ["git", *argumentos], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if chequear and resultado.returncode != 0:
        raise RuntimeError(f"git {' '.join(argumentos)}: {resultado.stderr.strip()}")
    return resultado


def preparar_worktree(rama, numero):
    carpeta = CARPETA_TRABAJO / f"issue-{numero}"
    git("fetch", "origin", "--prune")
    if carpeta.exists():
        git("worktree", "remove", "--force", str(carpeta), chequear=False)
        shutil.rmtree(carpeta, ignore_errors=True)
    git("worktree", "prune")
    git("worktree", "add", "-B", rama, str(carpeta), f"origin/{rama}")
    # Si hay conflictos con main, quedan en el árbol para que Codex los resuelva.
    git("merge", "origin/main", "--no-edit", cwd=carpeta, chequear=False)
    return carpeta


def correr_codex(carpeta, prompt):
    binario = binario_codex()
    if binario is None:
        raise RuntimeError("No encuentro Codex: definí GIMNASIO_CODEX_BIN con la ruta de codex.exe.")
    salida = carpeta / ".implementador-ultimo.txt"
    resultado = subprocess.run(
        [binario, "exec", "-C", str(carpeta), "-s", "workspace-write", "-c", 'model_reasoning_effort="high"']
        + ["-o", str(salida), "-"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=LIMITE_MINUTOS * 60,
    )
    texto = salida.read_text(encoding="utf-8").strip() if salida.exists() else resultado.stderr[-2000:]
    salida.unlink(missing_ok=True)
    return resultado.returncode, texto


def subir_cambios(carpeta, rama, titulo):
    """Commit y push de lo que dejó Codex; False si no tocó nada.

    La fusión limpia con main que hace `preparar_worktree` no cuenta: sin trabajo de Codex no hay nada que subir.
    """
    sucio = git("status", "--porcelain", cwd=carpeta).stdout.strip() != ""
    en_fusion = git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=carpeta, chequear=False).returncode == 0
    if not (sucio or en_fusion):
        return False
    git("add", "-A", cwd=carpeta)
    git("commit", "-m", titulo, cwd=carpeta)
    git("push", "origin", f"HEAD:{rama}", cwd=carpeta)
    return True


# --- Pasos -----------------------------------------------------------------


def atender(pr, pedido):
    numero, rama = pr["number"], pr["headRefName"]
    numero_issue = cadena.numero_de_rama(rama)
    carpeta = preparar_worktree(rama, numero_issue)
    codigo, texto = correr_codex(carpeta, prompt_para_codex(pedido))
    pregunta = cadena.pregunta_de_criterio(texto)
    if pregunta:
        cadena.gh("issue", "comment", str(numero_issue), "--body", f"Duda de Codex (PR #{numero}):\n\n> {pregunta}")
        cadena.etiquetar(
            numero_issue, agregar=["necesita-criterio"], quitar=["estado:en-curso", "agente:codex"], tipo="issue"
        )
        cadena.comentar(numero, f"{MARCA_HECHO}\nCodex tiene una duda de criterio; quedó en el issue #{numero_issue}.")
        return
    if codigo != 0 or not subir_cambios(carpeta, rama, f"{pr['title']} (#{numero_issue})"):
        raise RuntimeError(f"Codex terminó con código {codigo} y no dejó cambios que subir.\n\n{texto[-1500:]}")
    cadena.comentar(numero, f"{MARCA_HECHO}\nImplementado en esta PC con Codex.\n\n{texto[-1500:]}")
    git("worktree", "remove", "--force", str(carpeta), chequear=False)


def una_vuelta():
    for pr in cadena.prs_de_codex():
        if "bloqueado" in cadena.etiquetas_de(pr):
            continue
        pedido, fallos = pedido_pendiente(cadena.comentarios_del_pr(pr["number"]))
        if pedido is None or fallos >= MAX_FALLOS:
            if pedido is not None:
                cadena.etiquetar(pr["number"], agregar=["bloqueado"])
                cadena.comentar(
                    pr["number"], f"El implementador falló {MAX_FALLOS} veces: queda `bloqueado` para el dueño."
                )
            continue
        print(f"Atendiendo el PR #{pr['number']} ({pr['headRefName']})…")
        try:
            atender(pr, pedido)
        except Exception as error:  # un fallo no frena el ciclo: queda registrado en el PR
            print(f"Falló el PR #{pr['number']}: {error}", file=sys.stderr)
            cadena.comentar(pr["number"], f"{MARCA_FALLO}\nEl implementador falló:\n\n```\n{error}\n```")
        return True
    return False


def main(argv=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--esperar", action="store_true", help="repetir cada 60 segundos")
    args = analizador.parse_args(argv)
    os.environ.setdefault(
        "GITHUB_REPOSITORY", cadena.gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    )
    while True:
        trabajo = una_vuelta()
        if not args.esperar:
            return 0
        if not trabajo:
            time.sleep(ESPERA_SEGUNDOS)


if __name__ == "__main__":
    sys.exit(main())
