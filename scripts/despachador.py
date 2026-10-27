"""Despachador de issues hacia Codex y Opus (ver AGENTS.md y ADR 0011).

Cada vuelta:
1. Revisa los PR abiertos de ramas `agente/issue-N`: espera el CI, pide correcciones si falla,
   lanza la revisión cruzada y fusiona con squash cuando todo aprueba.
2. Toma issues `estado:listo` con dependencias cerradas, un solo issue activo por módulo,
   y los lanza en worktrees propios: hasta `max_codex` Codex y `max_claude` Claude a la vez.
3. Registra los tokens de cada corrida en .despachador/registro.jsonl y aplica el presupuesto de Opus.

Uso:
    python scripts/despachador.py --una-vuelta [--simular] [--solo-codex]
    python scripts/despachador.py --hasta-vaciar [--solo-codex]
    python scripts/despachador.py --informe
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

if os.name == "nt":
    import msvcrt
else:
    import fcntl

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = tomllib.loads((Path(__file__).with_suffix(".toml")).read_text(encoding="utf-8"))
REGISTRO = RAIZ / ".despachador" / "registro.jsonl"
CANDADO = RAIZ / ".despachador" / "corriendo.lock"
PREFIJO_RAMA = "agente/issue-"
MARCA_CRITERIO = "NECESITA-CRITERIO:"
ESQUEMA_REVISION = {
    "type": "object",
    "properties": {
        "hallazgos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "archivo": {"type": "string"},
                    "problema": {"type": "string"},
                    "gravedad": {"type": "string", "enum": ["bloqueante", "menor"]},
                },
                "required": ["archivo", "problema", "gravedad"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["hallazgos"],
    "additionalProperties": False,
}
_candado_git = threading.Lock()
_candado_registro = threading.Lock()


# ---------------------------------------------------------------- utilidades


def correr(comando, cwd=RAIZ, entrada=None, chequear=True, timeout=None):
    resultado = subprocess.run(
        comando,
        cwd=cwd,
        input=entrada,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if chequear and resultado.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, comando[:4]))}… falló: {resultado.stderr.strip()[:500]}")
    return resultado


def gh(*argumentos, entrada=None):
    return correr(["gh", *argumentos, "--repo", CONFIG["repo"]], entrada=entrada).stdout


def gh_json(*argumentos):
    return json.loads(gh(*argumentos) or "null")


def ahora():
    return datetime.now(UTC)


def registrar(entrada):
    REGISTRO.parent.mkdir(exist_ok=True)
    entrada = {"fecha": ahora().isoformat(timespec="seconds"), **entrada}
    with _candado_registro, REGISTRO.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def tomar_candado_instancia():
    """Un solo despachador a la vez: dos instancias revisaban el mismo PR en paralelo y duplicaban el gasto.

    Devuelve el archivo abierto, que hay que mantener vivo mientras corre, o None si otra instancia lo tiene.
    El sistema operativo suelta el candado cuando el proceso termina, aunque muera sin limpiar.
    """
    CANDADO.parent.mkdir(exist_ok=True)
    archivo = CANDADO.open("a+")
    try:
        if os.name == "nt":
            archivo.seek(0)
            msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(archivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        archivo.close()
        return None
    return archivo


def leer_registro():
    if not REGISTRO.exists():
        return []
    return [json.loads(linea) for linea in REGISTRO.read_text(encoding="utf-8").splitlines() if linea]


def tokens_ponderados(uso):
    peso = CONFIG["presupuesto"]["peso_lectura_cache"]
    return int(
        uso.get("entrada", 0) + uso.get("salida", 0) + uso.get("creacion_cache", 0) + peso * uso.get("lectura_cache", 0)
    )


def inicio_de_semana():
    zona = ZoneInfo(CONFIG["presupuesto"]["zona"])
    local = ahora().astimezone(zona)
    lunes = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return lunes.astimezone(UTC)


def consumo_semanal(ejecutor="opus"):
    desde = inicio_de_semana()
    return sum(
        e.get("ponderados", 0)
        for e in leer_registro()
        if e.get("ejecutor") == ejecutor and datetime.fromisoformat(e["fecha"]) >= desde
    )


def fraccion_presupuesto():
    return consumo_semanal("opus") / CONFIG["presupuesto"]["semanal_opus"]


# ---------------------------------------------------------------- issues


@dataclass
class Issue:
    numero: int
    titulo: str
    cuerpo: str
    etiquetas: set = field(default_factory=set)

    @classmethod
    def desde_gh(cls, datos):
        return cls(datos["number"], datos["title"], datos.get("body") or "", {e["name"] for e in datos["labels"]})

    def valor(self, prefijo):
        for etiqueta in self.etiquetas:
            if etiqueta.startswith(prefijo):
                return etiqueta.removeprefix(prefijo)
        return None

    @property
    def modulo(self):
        return self.valor("modulo:") or "sin-modulo"

    @property
    def ejecutor(self):
        return self.valor("ejecutor:") or "codex"

    @property
    def dependencias(self):
        linea = re.search(r"Depende de:\s*(.*)", self.cuerpo)
        return [int(n) for n in re.findall(r"#(\d+)", linea.group(1))] if linea else []

    @property
    def sensible(self):
        return self.modulo in CONFIG["rutas"]["modulos_sensibles"] or "tipo:patron" in self.etiquetas


def issues(etiqueta):
    datos = gh_json(
        "issue", "list", "--state", "open", "--label", etiqueta, "--limit", "100", "--json", "number,title,body,labels"
    )
    return [Issue.desde_gh(d) for d in datos]


def esta_cerrado(numero):
    return gh_json("issue", "view", str(numero), "--json", "state")["state"] == "CLOSED"


def etiquetar(numero, agregar=(), quitar=()):
    argumentos = ["issue", "edit", str(numero)]
    if agregar:
        argumentos += ["--add-label", ",".join(agregar)]
    if quitar:
        argumentos += ["--remove-label", ",".join(quitar)]
    gh(*argumentos)


def comentar(numero, texto):
    gh("issue", "comment", str(numero), "--body-file", "-", entrada=texto)


def intentos(numero, ejecutor):
    return sum(
        1
        for e in leer_registro()
        if e.get("issue") == numero and e.get("ejecutor") == ejecutor and e.get("fase") in ("implementar", "corregir")
    )


# ---------------------------------------------------------------- worktrees


def carpeta_de(numero):
    return (RAIZ / CONFIG["carpeta_trabajo"] / f"issue-{numero}").resolve()


def preparar_worktree(numero):
    carpeta, rama = carpeta_de(numero), f"{PREFIJO_RAMA}{numero}"
    with _candado_git:
        correr(["git", "fetch", "origin", "--prune"])
        remota = correr(["git", "ls-remote", "--heads", "origin", rama]).stdout.strip()
        base = f"origin/{rama}" if remota else f"origin/{CONFIG['rama_base']}"
        if carpeta.exists():
            # Sin rama remota, el intento anterior no publicó nada: se parte de main actualizado,
            # no del commit viejo en el que quedó la carpeta.
            correr(["git", "reset", "--hard", base], cwd=carpeta)
            correr(["git", "clean", "-fd"], cwd=carpeta)
            return carpeta
        correr(["git", "worktree", "add", "-B", rama, str(carpeta), base])
    return carpeta


def preparar_worktree_revision(numero):
    """Worktree desacoplado en la punta remota de la rama: no choca si la rama está tomada en otra carpeta."""
    carpeta = (RAIZ / CONFIG["carpeta_trabajo"] / f"revision-{numero}").resolve()
    punta = f"origin/{PREFIJO_RAMA}{numero}"
    with _candado_git:
        correr(["git", "fetch", "origin", "--prune"])
        if carpeta.exists():
            correr(["git", "checkout", "--detach", "--force", punta], cwd=carpeta)
        else:
            correr(["git", "worktree", "add", "--detach", str(carpeta), punta])
    return carpeta


def quitar_worktree(numero):
    carpetas = [carpeta_de(numero), (RAIZ / CONFIG["carpeta_trabajo"] / f"revision-{numero}").resolve()]
    with _candado_git:
        for carpeta in carpetas:
            if carpeta.exists():
                correr(["git", "worktree", "remove", "--force", str(carpeta)], chequear=False)
                shutil.rmtree(carpeta, ignore_errors=True)
        correr(["git", "worktree", "prune"], chequear=False)


def hay_cambios(carpeta):
    pendientes = correr(["git", "status", "--porcelain"], cwd=carpeta).stdout.strip()
    adelante = correr(["git", "rev-list", "--count", f"origin/{CONFIG['rama_base']}..HEAD"], cwd=carpeta)
    return bool(pendientes) or int(adelante.stdout.strip() or 0) > 0


# ---------------------------------------------------------------- agentes


def entorno_agente():
    entorno = dict(os.environ)
    scripts = RAIZ / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    entorno["PATH"] = f"{scripts}{os.pathsep}{entorno.get('PATH', '')}"
    return entorno


def correr_codex(carpeta, prompt, esquema=None):
    binario = os.environ.get("GIMNASIO_CODEX_BIN") or CONFIG["codex"]["binario"]
    salida = carpeta / ".despachador-ultimo.txt"
    comando = [binario, "exec", "--json", "-C", str(carpeta), "-o", str(salida)]
    for valor in CONFIG["codex"]["config_revision" if esquema else "config"]:
        comando += ["-c", valor]
    if esquema:
        archivo = carpeta / ".despachador-esquema.json"
        archivo.write_text(json.dumps(esquema), encoding="utf-8")
        comando += ["--output-schema", str(archivo), "-s", "read-only"]
    else:
        comando += ["-s", CONFIG["codex"]["sandbox"]]
    comando.append("-")
    resultado = subprocess.run(
        comando,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=entorno_agente(),
        timeout=CONFIG["limite_minutos_por_tarea"] * 60,
    )
    uso = {"entrada": 0, "salida": 0, "lectura_cache": 0, "creacion_cache": 0}
    for linea in resultado.stdout.splitlines():
        try:
            evento = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if evento.get("type") == "turn.completed":
            u = evento.get("usage", {})
            cache = u.get("cached_input_tokens", 0)
            uso["entrada"] += u.get("input_tokens", 0) - cache
            uso["lectura_cache"] += cache
            uso["creacion_cache"] += u.get("cache_write_input_tokens", 0)
            uso["salida"] += u.get("output_tokens", 0)
    texto = salida.read_text(encoding="utf-8") if salida.exists() else resultado.stderr[-2000:]
    for temporal in (salida, carpeta / ".despachador-esquema.json"):
        temporal.unlink(missing_ok=True)
    return resultado.returncode, texto.strip(), uso


def correr_claude(carpeta, prompt, esquema=None, solo_lectura=False):
    configuracion = CONFIG["claude"]
    comando = [
        os.environ.get("GIMNASIO_CLAUDE_BIN") or shutil.which(configuracion["binario"]),
        "-p",
        "--model",
        configuracion["modelo"],
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    if solo_lectura:
        comando += ["--permission-mode", "dontAsk", "--allowedTools", "Read", "Grep", "Glob"]
    else:
        comando += ["--permission-mode", configuracion["modo_permisos"]]
    if esquema:
        comando += ["--json-schema", json.dumps(esquema)]
    resultado = subprocess.run(
        comando,
        input=prompt,
        cwd=carpeta,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=entorno_agente(),
        timeout=CONFIG["limite_minutos_por_tarea"] * 60,
    )
    try:
        datos = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        return 1, (resultado.stdout + resultado.stderr)[-2000:], {}
    u = datos.get("usage", {})
    uso = {
        "entrada": u.get("input_tokens", 0),
        "salida": u.get("output_tokens", 0),
        "lectura_cache": u.get("cache_read_input_tokens", 0),
        "creacion_cache": u.get("cache_creation_input_tokens", 0),
        "costo_usd": datos.get("total_cost_usd", 0),
    }
    texto = datos.get("structured_output")
    texto = json.dumps(texto) if texto is not None else datos.get("result", "")
    codigo = 1 if datos.get("is_error") else resultado.returncode
    return codigo, texto.strip(), uso


def correr_agente(ejecutor, carpeta, prompt, **opciones):
    if ejecutor == "opus":
        return correr_claude(carpeta, prompt, **opciones)
    opciones.pop("solo_lectura", None)
    return correr_codex(carpeta, prompt, **opciones)


INSTRUCCIONES = """Sos un agente de Gimnasio Pro. Leé AGENTS.md y solo los ADR que cite el issue.
Trabajás en un worktree de la rama {rama}. No hagas commit ni push: el despachador lo hace.
Corré `ruff check .`, `ruff format .` y `pytest` antes de terminar.
Si el issue es ambiguo en algo de producto, no adivines: terminá con un mensaje que empiece con
"{marca}" y explique la duda, sin dejar cambios a medias.
Si terminás, tu mensaje final es el cuerpo del PR en markdown, siguiendo .github/pull_request_template.md,
empezando por "Closes #{numero}" y con la sección "Notas para el próximo agente".
"""


def prompt_implementar(issue):
    return (
        INSTRUCCIONES.format(rama=f"{PREFIJO_RAMA}{issue.numero}", marca=MARCA_CRITERIO, numero=issue.numero)
        + f"\n# Issue #{issue.numero}: {issue.titulo}\n\n{issue.cuerpo}\n"
    )


def prompt_corregir(issue, motivo):
    return (
        prompt_implementar(issue)
        + "\n# Corrección pedida\nLa rama ya tiene tu trabajo anterior. Corregí solo esto:\n\n"
        + motivo
        + "\n"
    )


FOCO_SENSIBLE = "Rutas sensibles: revisá reglas, frenos, permisos, salud y migraciones con especial cuidado.\n"
CRITERIO_BLOQUEANTE = (
    "Es bloqueante solo un error, una violación de ADR, una prueba que falta, un secreto o un término fuera del "
    "glosario; todo lo demás es menor. El PR se aprueba si no queda ningún bloqueante. "
)


def lista_hallazgos(hallazgos):
    return "\n".join(f"- **{h['gravedad']}** `{h['archivo']}`: {h['problema']}" for h in hallazgos)


def prompt_revisar(issue, diff, resumen_ci, sensible):
    return (
        "Revisá este PR de Gimnasio Pro contra AGENTS.md y el issue. Leé el diff; abrí otros archivos solo si "
        "hace falta. "
        + CRITERIO_BLOQUEANTE
        + "Respondé solo con el JSON pedido.\n"
        + (FOCO_SENSIBLE if sensible else "")
        + f"\n# Issue #{issue.numero}: {issue.titulo}\n{issue.cuerpo}\n\n# Resumen del CI\n{resumen_ci}\n"
        + f"\n# Diff\n```diff\n{diff[:150_000]}\n```\n"
    )


def prompt_revisar_de_nuevo(issue, diff, hallazgos, resumen_ci, sensible):
    """De la segunda ronda en adelante: se verifica lo pedido y lo que cambió, sin volver a revisar todo el PR."""
    return (
        "Volvé a revisar este PR de Gimnasio Pro. Ya lo revisaste: abajo están tus hallazgos anteriores y el diff "
        "de lo que cambió desde entonces. Verificá cada bloqueante anterior: si sigue sin resolver, repetilo. "
        "Un hallazgo nuevo cuenta solo si está en este diff. "
        + CRITERIO_BLOQUEANTE
        + "Abrí otros archivos solo si hace falta. Respondé solo con el JSON pedido.\n"
        + (FOCO_SENSIBLE if sensible else "")
        + f"\n# Issue #{issue.numero}: {issue.titulo}\n{issue.cuerpo}\n"
        + f"\n# Hallazgos anteriores\n{lista_hallazgos(hallazgos)}\n\n# Resumen del CI\n{resumen_ci}\n"
        + f"\n# Diff desde la revisión anterior\n```diff\n{diff[:150_000]}\n```\n"
    )


# ---------------------------------------------------------------- tareas


def implementar(issue, ejecutor, motivo=None):
    fase = "corregir" if motivo else "implementar"
    inicio = time.monotonic()
    carpeta = preparar_worktree(issue.numero)
    prompt = prompt_corregir(issue, motivo) if motivo else prompt_implementar(issue)
    try:
        codigo, texto, uso = correr_agente(ejecutor, carpeta, prompt)
    except subprocess.TimeoutExpired:
        codigo, texto, uso = 1, "Se agotó el tiempo de la tarea.", {}
    registrar(
        {
            "issue": issue.numero,
            "ejecutor": ejecutor,
            "fase": fase,
            "uso": uso,
            "ponderados": tokens_ponderados(uso),
            "segundos": int(time.monotonic() - inicio),
            "codigo": codigo,
        }
    )
    if texto.startswith(MARCA_CRITERIO):
        etiquetar(
            issue.numero,
            ["necesita-criterio", "ejecutor:opus"],
            ["estado:en-curso", "ejecutor:codex", f"agente:{ejecutor}"],
        )
        comentar(issue.numero, texto)
        return
    if codigo != 0 or not hay_cambios(carpeta):
        fallar(issue, ejecutor, f"La corrida terminó sin cambios utilizables (código {codigo}).\n\n{texto[-1500:]}")
        return
    publicar(issue, ejecutor, carpeta, texto)
    etiquetar(issue.numero, ["estado:revision"], ["estado:en-curso", f"agente:{ejecutor}"])


def fallar(issue, ejecutor, detalle):
    maximo = CONFIG["intentos_max_opus"] if ejecutor == "opus" else CONFIG["intentos_max_codex"]
    quitar = ["estado:en-curso", f"agente:{ejecutor}"]
    if intentos(issue.numero, ejecutor) >= maximo:
        agregar = ["bloqueado"] + ([] if ejecutor == "opus" else ["ejecutor:opus"])
        quitar += [] if ejecutor == "opus" else ["ejecutor:codex"]
        etiquetar(issue.numero, agregar, quitar)
        comentar(issue.numero, f"Bloqueado tras {maximo} intentos de {ejecutor}.\n\n{detalle}")
    else:
        etiquetar(issue.numero, ["estado:listo"], quitar)
        comentar(issue.numero, f"Intento fallido de {ejecutor}; se reintentará.\n\n{detalle}")


def publicar(issue, ejecutor, carpeta, cuerpo):
    rama = f"{PREFIJO_RAMA}{issue.numero}"
    if not re.search(rf"(?i)\b(closes|fixes|resolves) #{issue.numero}\b", cuerpo):
        cuerpo = f"Closes #{issue.numero}\n\n{cuerpo}"
    correr(["git", "add", "-A"], cwd=carpeta)
    if correr(["git", "diff", "--cached", "--quiet"], cwd=carpeta, chequear=False).returncode != 0:
        correr(["git", "commit", "-m", f"{issue.titulo} (#{issue.numero})", "-m", f"Ejecutor: {ejecutor}"], cwd=carpeta)
    correr(["git", "push", "-u", "origin", rama, "--force-with-lease"], cwd=carpeta)
    existente = gh_json("pr", "list", "--head", rama, "--state", "open", "--json", "number")
    if existente:
        gh("pr", "comment", str(existente[0]["number"]), "--body-file", "-", entrada=cuerpo)
        gh("pr", "edit", str(existente[0]["number"]), "--remove-label", "revisado:codex,revisado:opus")
    else:
        gh(
            "pr",
            "create",
            "--base",
            CONFIG["rama_base"],
            "--head",
            rama,
            "--title",
            f"{issue.titulo} (#{issue.numero})",
            "--body-file",
            "-",
            entrada=cuerpo,
        )


def resumen_ci(numero_pr):
    comentarios = gh_json("pr", "view", str(numero_pr), "--json", "comments")["comments"]
    for comentario in reversed(comentarios):
        if "<!-- resumen-ci -->" in comentario["body"]:
            return comentario["body"]
    return "(sin resumen del CI)"


def toca_sensibles(numero_pr):
    archivos = gh("pr", "diff", str(numero_pr), "--name-only").split()
    return any(a.startswith(tuple(CONFIG["rutas"]["sensibles"])) for a in archivos)


def ultima_revision(numero_pr, revisor):
    """La última revisión con veredicto de este revisor sobre el PR, si guardó el commit y los hallazgos."""
    for entrada in reversed(leer_registro()):
        if entrada.get("fase") != "revisar" or entrada.get("pr") != numero_pr or entrada.get("ejecutor") != revisor:
            continue
        if not entrada.get("fallida") and entrada.get("commit") and entrada.get("hallazgos") is not None:
            return entrada
    return None


def diff_incremental(carpeta, numero_pr, commit):
    """Cambios desde el commit ya revisado, solo en archivos del PR: lo que trae main al integrarse queda afuera.

    Devuelve None si la rama se reescribió y ese commit ya no es ancestro: entonces se revisa el diff completo.
    """
    if correr(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=carpeta, chequear=False).returncode != 0:
        return None
    archivos = gh("pr", "diff", str(numero_pr), "--name-only").split()
    return correr(["git", "diff", commit, "HEAD", "--", *archivos], cwd=carpeta).stdout


def leer_hallazgos(texto):
    """Los hallazgos del veredicto, o None si la salida no es el JSON pedido."""
    try:
        veredicto = json.loads(texto)
    except json.JSONDecodeError:
        return None
    if not isinstance(veredicto, dict) or not isinstance(veredicto.get("hallazgos"), list):
        return None
    return veredicto["hallazgos"]


def aprobado(hallazgos):
    # Lo decide el script y no el modelo: un PR con solo hallazgos menores se aprueba siempre.
    return all(h["gravedad"] != "bloqueante" for h in hallazgos)


def revisar(issue, pr, revisor):
    inicio = time.monotonic()
    carpeta = preparar_worktree_revision(issue.numero)
    numero = pr["number"]
    sensible = toca_sensibles(numero)
    commit = correr(["git", "rev-parse", "HEAD"], cwd=carpeta).stdout.strip()
    anterior = ultima_revision(numero, revisor)
    diff = diff_incremental(carpeta, numero, anterior["commit"]) if anterior else None
    if diff is None:
        prompt = prompt_revisar(issue, gh("pr", "diff", str(numero)), resumen_ci(numero), sensible)
    else:
        prompt = prompt_revisar_de_nuevo(issue, diff, anterior["hallazgos"], resumen_ci(numero), sensible)
    try:
        _, texto, uso = correr_agente(revisor, carpeta, prompt, esquema=ESQUEMA_REVISION, solo_lectura=True)
    except subprocess.TimeoutExpired:
        texto, uso = "tiempo agotado", {}
    hallazgos = leer_hallazgos(texto)
    registrar(
        {
            "issue": issue.numero,
            "pr": numero,
            "ejecutor": revisor,
            "fase": "revisar",
            "uso": uso,
            "ponderados": tokens_ponderados(uso),
            "segundos": int(time.monotonic() - inicio),
            "fallida": hallazgos is None,
            "incremental": diff is not None,
            "commit": commit,
            "hallazgos": hallazgos,
        }
    )
    if hallazgos is None:
        # Se reintenta en la próxima vuelta, pero no sin fin: tras varias seguidas se bloquea con el error a la vista.
        if revisiones_fallidas_seguidas(pr["number"]) >= CONFIG["revisiones_fallidas_max"]:
            etiquetar(issue.numero, ["bloqueado"], [])
            comentar(
                issue.numero,
                f"Bloqueado: {CONFIG['revisiones_fallidas_max']} revisiones seguidas de {revisor} sin veredicto "
                f"en el PR #{pr['number']}. Última salida:\n\n```\n{texto[-1500:]}\n```",
            )
        return
    if aprobado(hallazgos):
        gh("pr", "edit", str(numero), "--add-label", f"revisado:{revisor}")
        if hallazgos:
            gh(
                "pr",
                "comment",
                str(numero),
                "--body-file",
                "-",
                entrada=f"Revisión de {revisor}: aprobado con observaciones menores.\n\n{lista_hallazgos(hallazgos)}",
            )
    else:
        motivo = f"Revisión de {revisor}: cambios pedidos.\n\n{lista_hallazgos(hallazgos)}"
        gh("pr", "comment", str(numero), "--body-file", "-", entrada=motivo)
        corregir_o_bloquear(issue, motivo)


GENERADOS = {"docs/MAPA-CAPACIDADES.md"}


def integrar_main(issue):
    """Integra origin/main en la rama sin gastar tokens si solo chocan archivos generados; si no, pide corrección."""
    carpeta = preparar_worktree(issue.numero)
    with _candado_git:
        fusion = correr(["git", "merge", "--no-edit", f"origin/{CONFIG['rama_base']}"], cwd=carpeta, chequear=False)
        conflictos = set(correr(["git", "diff", "--name-only", "--diff-filter=U"], cwd=carpeta).stdout.split())
        if fusion.returncode != 0 and not conflictos:
            # Falló por otra causa (archivos locales que se sobrescribirían, etc.): no se empuja nada.
            correr(["git", "merge", "--abort"], cwd=carpeta, chequear=False)
            corregir_o_bloquear(issue, f"No se pudo integrar main: {fusion.stderr.strip()[:1500]}")
            return
        if conflictos - GENERADOS:
            correr(["git", "merge", "--abort"], cwd=carpeta, chequear=False)
            lista = ", ".join(sorted(conflictos - GENERADOS))
            corregir_o_bloquear(issue, f"Conflicto con main en: {lista}. Integrá origin/main y resolvé los conflictos.")
            return
        python = RAIZ / ".venv" / ("Scripts" if os.name == "nt" else "bin") / "python"
        correr([str(python), "scripts/mapa_capacidades.py"], cwd=carpeta)
        correr(["git", "add", "-A"], cwd=carpeta)
        # Si la fusión fue limpia ya quedó commiteada y no hay nada más que confirmar.
        correr(
            ["git", "commit", "--no-edit", "-m", "Integrar main y regenerar archivos generados"],
            cwd=carpeta,
            chequear=False,
        )
        correr(["git", "push", "origin", f"{PREFIJO_RAMA}{issue.numero}"], cwd=carpeta)
    registrar({"issue": issue.numero, "ejecutor": "script", "fase": "integrar-main", "uso": {}, "ponderados": 0})


def revisiones_fallidas_seguidas(numero_pr):
    seguidas = 0
    for entrada in leer_registro():
        if entrada.get("fase") == "revisar" and entrada.get("pr") == numero_pr:
            seguidas = seguidas + 1 if entrada.get("fallida") else 0
    return seguidas


def corregir_o_bloquear(issue, motivo):
    ejecutor = issue.ejecutor
    maximo = CONFIG["intentos_max_opus"] if ejecutor == "opus" else CONFIG["intentos_max_codex"]
    if intentos(issue.numero, ejecutor) >= maximo:
        agregar = ["bloqueado"] + ([] if ejecutor == "opus" else ["ejecutor:opus"])
        quitar = ["estado:revision"] + ([] if ejecutor == "opus" else ["ejecutor:codex"])
        etiquetar(issue.numero, agregar, quitar)
        comentar(issue.numero, f"Bloqueado: se agotaron los intentos de {ejecutor}.\n\n{motivo[:3000]}")
    else:
        etiquetar(issue.numero, ["estado:en-curso", "correccion-pendiente"], ["estado:revision"])
        comentar(issue.numero, f"<!-- correccion -->\n{motivo[:6000]}")


# ---------------------------------------------------------------- planificador


@dataclass
class Plan:
    acciones: list = field(default_factory=list)  # (tipo, issue, ejecutor, extra)
    avisos: list = field(default_factory=list)


def estado_checks(numero_pr):
    # Justo después de un push, gh todavía no ve checks y sale con error: eso es "pendiente", no una falla.
    resultado = correr(
        ["gh", "pr", "checks", str(numero_pr), "--json", "name,bucket", "--repo", CONFIG["repo"]], chequear=False
    )
    try:
        checks = json.loads(resultado.stdout or "[]")
    except json.JSONDecodeError:
        checks = []
    cubetas = {c["bucket"] for c in checks if c["name"] != "resumen"}
    if not checks or "pending" in cubetas:
        return "pendiente"
    return "falla" if cubetas & {"fail", "cancel"} else "ok"


def planificar(ocupados, libres, solo_codex):
    plan, fraccion = Plan(), fraccion_presupuesto()
    if fraccion >= CONFIG["presupuesto"]["aviso"]:
        plan.avisos.append(f"Opus al {fraccion:.0%} del presupuesto semanal")
    puede_opus = not solo_codex and fraccion < CONFIG["presupuesto"]["corte"]

    def reservar(ejecutor):
        if ejecutor == "opus" and not puede_opus:
            return False
        if libres[ejecutor] <= 0:
            return False
        libres[ejecutor] -= 1
        return True

    # 1. Correcciones pedidas por CI o revisión.
    for issue in issues("correccion-pendiente"):
        if issue.numero in ocupados or {"bloqueado", "necesita-criterio"} & issue.etiquetas:
            continue
        if issue.ejecutor == "opus" and fraccion >= CONFIG["presupuesto"]["aviso"] and not issue.sensible:
            continue
        if reservar(issue.ejecutor):
            comentarios = gh_json("issue", "view", str(issue.numero), "--json", "comments")["comments"]
            motivo = next((c["body"] for c in reversed(comentarios) if "<!-- correccion -->" in c["body"]), "")
            plan.acciones.append(("corregir", issue, issue.ejecutor, motivo))

    # 2. PR en revisión: CI, revisión cruzada y fusión.
    for issue in issues("estado:revision"):
        if issue.numero in ocupados or "bloqueado" in issue.etiquetas:
            continue
        prs = gh_json(
            "pr",
            "list",
            "--head",
            f"{PREFIJO_RAMA}{issue.numero}",
            "--state",
            "open",
            "--json",
            "number,labels,mergeable",
        )
        if not prs:
            continue
        pr = prs[0]
        # Con conflictos GitHub no corre el CI: hay que integrar main antes de esperar los checks.
        if pr["mergeable"] == "CONFLICTING":
            plan.acciones.append(("integrar-main", issue, None, pr))
            continue
        estado = estado_checks(pr["number"])
        if estado == "pendiente":
            continue
        if estado == "falla":
            plan.acciones.append(("ci-fallido", issue, issue.ejecutor, pr))
            continue
        etiquetas_pr = {e["name"] for e in pr["labels"]}
        faltan = [] if "revisado:codex" in etiquetas_pr else ["codex"]
        if "revisado:opus" not in etiquetas_pr and toca_sensibles(pr["number"]):
            faltan.append("opus")
        if not faltan:
            plan.acciones.append(("fusionar", issue, None, pr))
        elif reservar(faltan[0]):
            plan.acciones.append(("revisar", issue, faltan[0], pr))

    # 3. Issues listos.
    activos = {i.modulo for i in issues("estado:en-curso") + issues("estado:revision")}
    for issue in sorted(issues("estado:listo"), key=lambda i: i.numero):
        if issue.numero in ocupados or {"bloqueado", "necesita-criterio"} & issue.etiquetas:
            continue
        if issue.modulo in activos:
            continue
        if any(not esta_cerrado(n) for n in issue.dependencias):
            continue
        ejecutor = issue.ejecutor
        if ejecutor == "opus" and fraccion >= CONFIG["presupuesto"]["corte"] and not issue.sensible:
            plan.acciones.append(("pasar-a-codex", issue, "codex", None))
            continue
        if ejecutor == "opus" and fraccion >= CONFIG["presupuesto"]["aviso"] and not issue.sensible:
            continue
        if reservar(ejecutor):
            activos.add(issue.modulo)
            plan.acciones.append(("implementar", issue, ejecutor, None))
    return plan


def ejecutar_accion(accion):
    """Ejecuta una acción; si algo falla, devuelve el issue a la cola en vez de dejarlo con el candado puesto."""
    tipo, issue, ejecutor, _ = accion
    try:
        _ejecutar_accion(accion)
    except Exception as error:
        detalle = f"Error del despachador en `{tipo}`: {error}"
        if tipo in ("implementar", "corregir"):
            registrar(
                {"issue": issue.numero, "ejecutor": ejecutor, "fase": tipo, "uso": {}, "ponderados": 0, "codigo": -1}
            )
            fallar(issue, ejecutor, detalle)
        else:
            comentar(issue.numero, detalle)
        raise


def _ejecutar_accion(accion):
    tipo, issue, ejecutor, extra = accion
    if tipo == "implementar":
        etiquetar(issue.numero, ["estado:en-curso", f"agente:{ejecutor}"], ["estado:listo"])
        implementar(issue, ejecutor)
    elif tipo == "corregir":
        etiquetar(issue.numero, [f"agente:{ejecutor}"], ["correccion-pendiente"])
        implementar(issue, ejecutor, motivo=extra)
    elif tipo == "integrar-main":
        integrar_main(issue)
    elif tipo == "ci-fallido":
        corregir_o_bloquear(issue, f"El CI falló.\n\n{resumen_ci(extra['number'])}")
    elif tipo == "revisar":
        revisar(issue, extra, ejecutor)
    elif tipo == "fusionar":
        try:
            try:
                gh("pr", "merge", str(extra["number"]), "--squash", "--delete-branch")
            except RuntimeError as error:
                # Carrera con otra fusión recién hecha: no es un conflicto, se reintenta una vez.
                if "Base branch was modified" not in str(error):
                    raise
                time.sleep(15)
                gh("pr", "merge", str(extra["number"]), "--squash", "--delete-branch")
        except RuntimeError as error:
            motivo = "No se pudo fusionar (¿conflicto con main?). Integrá origin/main y resolvé los conflictos."
            corregir_o_bloquear(issue, f"{motivo}\n\n{error}")
            return
        etiquetar(issue.numero, [], ["estado:revision"])
        # Respaldo por si el PR no tenía la palabra clave de cierre.
        if not esta_cerrado(issue.numero):
            gh("issue", "close", str(issue.numero), "--comment", f"Fusionado en #{extra['number']}.")
        quitar_worktree(issue.numero)
    elif tipo == "pasar-a-codex":
        etiquetar(issue.numero, ["ejecutor:codex"], ["ejecutor:opus"])
        comentar(
            issue.numero,
            "Presupuesto de Opus agotado (ADR 0011): pasa a Codex. "
            "Codex: si falta detalle, etiquetá necesita-criterio.",
        )


def describir(accion):
    tipo, issue, ejecutor, _ = accion
    return f"{tipo:<14} #{issue.numero:<4} {ejecutor or '-':<6} {issue.titulo}"


def ciclo(argumentos):
    corriendo = {}  # número de issue -> (future, ejecutor)
    with ThreadPoolExecutor(max_workers=CONFIG["max_codex"] + CONFIG["max_claude"] + 4) as hilos:
        while True:
            for numero, (futuro, _) in list(corriendo.items()):
                if futuro.done():
                    error = futuro.exception()
                    if error:
                        print(f"#{numero}: error {error}", file=sys.stderr)
                    del corriendo[numero]
            libres = {
                "codex": CONFIG["max_codex"] - sum(e == "codex" for _, e in corriendo.values()),
                "opus": CONFIG["max_claude"] - sum(e == "opus" for _, e in corriendo.values()),
            }
            try:
                plan = planificar(set(corriendo), libres, argumentos.solo_codex)
            except RuntimeError as error:
                # Un fallo transitorio de gh no debe tirar abajo el ciclo: se reintenta en la próxima vuelta.
                print(f"Error al planificar, se reintenta: {error}", file=sys.stderr)
                time.sleep(CONFIG["espera_segundos"])
                continue
            for aviso in plan.avisos:
                print(f"Aviso: {aviso}")
            for accion in plan.acciones:
                print(describir(accion))
                if not argumentos.simular:
                    corriendo[accion[1].numero] = (hilos.submit(ejecutar_accion, accion), accion[2])
            if argumentos.una_vuelta or argumentos.simular:
                for futuro, _ in corriendo.values():
                    futuro.result()
                return 0
            if not corriendo and not plan.acciones and not issues("estado:revision"):
                print("Cola vacía.")
                return 0
            time.sleep(CONFIG["espera_segundos"])


def informe():
    por_ejecutor = {}
    for entrada in leer_registro():
        datos = por_ejecutor.setdefault(entrada["ejecutor"], {"corridas": 0, "ponderados": 0, "uso": {}})
        datos["corridas"] += 1
        datos["ponderados"] += entrada.get("ponderados", 0)
        for clave, valor in entrada.get("uso", {}).items():
            datos["uso"][clave] = round(datos["uso"].get(clave, 0) + valor, 4)
    print(json.dumps(por_ejecutor, indent=2, ensure_ascii=False))
    print(f"Opus esta semana: {consumo_semanal('opus'):,} ponderados ({fraccion_presupuesto():.1%})")
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    analizador = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = analizador.add_mutually_exclusive_group(required=True)
    modo.add_argument("--una-vuelta", action="store_true")
    modo.add_argument("--hasta-vaciar", action="store_true")
    modo.add_argument("--informe", action="store_true")
    analizador.add_argument("--simular", action="store_true", help="muestra el plan sin ejecutar nada")
    analizador.add_argument("--solo-codex", action="store_true", help="no lanza Claude (otro Claude ya está activo)")
    argumentos = analizador.parse_args()
    if argumentos.informe:
        return informe()
    candado = None if argumentos.simular else tomar_candado_instancia()
    if not argumentos.simular and candado is None:
        print(f"Ya hay otro despachador corriendo ({CANDADO.relative_to(RAIZ)}).", file=sys.stderr)
        return 1
    try:
        return ciclo(argumentos)
    finally:
        if candado:
            candado.close()


if __name__ == "__main__":
    sys.exit(main())
