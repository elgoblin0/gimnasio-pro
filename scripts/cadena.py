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
  python scripts/cadena.py vigilar
  python scripts/cadena.py cierre --issue 145
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PREFIJO_RAMA = "codex/issue-"
BOT_CODEX = "chatgpt-codex-connector[bot]"
BOT_OPUS = "claude[bot]"
RUTAS_SENSIBLES = (
    "gimnasio/reglas/",
    "migraciones/",
    "gimnasio/comun/migrar.py",
    "gimnasio/permisos/",
    "gimnasio/salud/",
)
PREFIJO_ADR = "opus/adr-"
RUTAS_ADR = ("docs/adr/", "GLOSSARY.md")
# Un tope por origen: en #135 una corrección de Opus agotó el tope compartido y el PR quedó bloqueado dos horas.
# Opus tiene el más bajo porque cada vuelta suya gasta cupo de Claude.
MAX_CORRECCIONES = {"ci": 3, "revision": 3, "opus": 2, "conflicto": 3}
ORIGENES = {
    "ci": "CI en rojo",
    "revision": "la revisión de Codex",
    "opus": "la revisión de Opus",
    "conflicto": "conflictos con main",
}
MARCA_CORREGIR = "<!-- cadena:corregir -->"
MARCA_ORIGEN = "<!-- cadena:origen {origen} -->"
MARCA_CONFLICTO = "<!-- cadena:conflicto {sha} -->"
# Issues en curso a la vez; el segundo solo si no comparte `modulo:` con el primero (ver elegir_siguiente).
MAX_EN_CURSO = int(os.environ.get("CADENA_EN_CURSO", "2"))
PREFIJO_MODULO = "modulo:"
CUERPO_FUSION = "Fusionado por la cadena (scripts/cadena.py)."
MARCA_PEDIDO = "<!-- cadena:pedido -->"
ENCABEZADO_LOCAL = "Pedido para el implementador local:"
MARCA_REVISAR = "<!-- cadena:revisar {sha} -->"
APROBACION_CODEX = "didn't find any major issues"
PEDIDO_CRITERIO = "NECESITA-CRITERIO:"
MARCA_HECHO = "<!-- implementador:hecho -->"
MARCA_FALLO = "<!-- implementador:fallo -->"
MARCA_AVISO = "<!-- cadena:aviso-demora -->"
MARCA_INFORME = "<!-- cadena:informe-etapa -->"
# El implementador pone 👀 al pedido que toma. Sin tomar: se espera menos que su sondeo de 60 s con margen.
# Tomado: Codex tiene hasta 60 minutos por intento.
SIN_TOMAR_MINUTOS = 15
COLGADO_MINUTOS = 75


# --- Lógica pura -----------------------------------------------------------


def dependencias(cuerpo):
    linea = re.search(r"Depende de:\s*(.*)", cuerpo or "")
    return [int(n) for n in re.findall(r"#(\d+)", linea.group(1))] if linea else []


def modulos(etiquetas):
    return {e for e in etiquetas if e.startswith(PREFIJO_MODULO)}


def choca(etiquetas, otras):
    """Dos issues chocan si comparten un `modulo:`; sin módulos no se sabe qué tocan y se asume que chocan."""
    return not modulos(etiquetas) or not modulos(otras) or bool(modulos(etiquetas) & modulos(otras))


def elegir_siguiente(issues, esta_cerrado, en_curso=()):
    """El issue listo de número más bajo con las dependencias cerradas que no choca con los `en_curso`.

    `en_curso` son los conjuntos de etiquetas de los issues que ya tienen un PR abierto.
    """
    for issue in sorted(issues, key=lambda i: i["number"]):
        etiquetas = {e["name"] for e in issue.get("labels", [])}
        if any(choca(etiquetas, otras) for otras in en_curso):
            continue
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


def aprobacion_de_opus(eventos):
    """La última vez que se puso `revisado:opus`, de los eventos del PR en orden, o None."""
    puestas = [e for e in eventos if e["event"] == "labeled" and e["label"]["name"] == "revisado:opus"]
    return puestas[-1] if puestas else None


def revisiones_a_descartar(revisiones, aprobacion):
    """Los pedidos de cambios vigentes de Opus anteriores a su aprobación.

    Opus aprueba con una etiqueta, sin revisión formal: su pedido de cambios sigue vigente y GitHub frena la fusión
    (#191). Uno posterior a la aprobación es un cambio de opinión y sigue frenando; los de otras cuentas no se tocan.
    """
    if aprobacion is None:
        return []
    return [
        r
        for r in revisiones
        if r["state"] == "CHANGES_REQUESTED"
        and (r["user"] or {}).get("login") == BOT_OPUS
        and fecha(r["submitted_at"]) < fecha(aprobacion["created_at"])
    ]


def encabezado_de_pedido():
    """`@codex` solo si CADENA_MENCIONAR_CODEX=1 (cuando Codex cloud vuelva a atender pedidos).

    Mientras los atienda el implementador local, mencionar a Codex solo trae su respuesta «create an environment».
    """
    return "@codex" if os.environ.get("CADENA_MENCIONAR_CODEX") == "1" else ENCABEZADO_LOCAL


def prompt_implementar(issue):
    # Solo AGENTS.md: el protocolo describe la orquestación, que Codex no hace, y leerlo gasta cupo en cada pedido.
    return (
        f"{MARCA_PEDIDO}\n{encabezado_de_pedido()} implementá el issue #{issue['number']} en esta rama, "
        "según AGENTS.md. Corré ruff y pytest antes de subir.\n"
        f"Si te falta una decisión de diseño, producto, alcance o término, no implementes: respondé "
        f"con una sola línea que empiece con `{PEDIDO_CRITERIO}` y la duda con tu recomendación.\n\n"
        f"## {issue['title']}\n\n{issue['body']}"
    )


def prompt_corregir(motivo, origen):
    return (
        f"{MARCA_CORREGIR}\n{MARCA_ORIGEN.format(origen=origen)}\n{encabezado_de_pedido()} {motivo} "
        "Subí la corrección a esta rama sin salirte del alcance del issue."
    )


def correcciones_pedidas(comentarios, origen):
    """Los pedidos de corrección de ese origen; los de antes de separar los topes no llevan origen y no cuentan."""
    marca = MARCA_ORIGEN.format(origen=origen)
    return sum(MARCA_CORREGIR in c and marca in c for c in comentarios)


def origen_de(pedido):
    """El origen de un pedido de corrección («ci», «revision»…), o None si es un pedido de implementar."""
    encontrado = re.search(r"<!-- cadena:origen (\w+) -->", pedido or "")
    return encontrado[1] if encontrado else None


def fecha(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def pedido_en_espera(comentarios):
    """El último pedido que el implementador no cerró con «hecho», o None. Comentarios como los da la API REST.

    `desde` es la última señal del implementador (el pedido o su último fallo, tras el cual reintenta);
    `avisado`, si ya se avisó la demora de este pedido.
    """
    pendiente = None
    for comentario in comentarios:
        cuerpo = comentario["body"] or ""
        if MARCA_HECHO in cuerpo:
            pendiente = None
        elif MARCA_PEDIDO in cuerpo or MARCA_CORREGIR in cuerpo:
            pendiente = {**comentario, "desde": comentario["created_at"], "avisado": False}
        elif pendiente is not None and MARCA_FALLO in cuerpo:
            pendiente["desde"] = comentario["created_at"]
        elif pendiente is not None and MARCA_AVISO in cuerpo:
            pendiente["avisado"] = True
    return pendiente


def tomado(pedido):
    return (pedido.get("reactions") or {}).get("eyes", 0) > 0


def demora(pedido, ahora, ocupado):
    """«sin-tomar», «colgado» o None. `ocupado`: el implementador ya trabaja en otro pedido, y esperar es normal."""
    if pedido is None or pedido["avisado"]:
        return None
    minutos = (ahora - fecha(pedido["desde"])).total_seconds() / 60
    if tomado(pedido):
        return "colgado" if minutos >= COLGADO_MINUTOS else None
    if ocupado:
        return None
    return "sin-tomar" if minutos >= SIN_TOMAR_MINUTOS else None


def issue_de_cierre(issues):
    """El issue «Cierre de etapa …» entre los de Opus de la etapa, o None."""
    return next((i for i in issues if i["title"].lower().startswith("cierre de etapa")), None)


def mensaje_rama_vacia(rama):
    """`[skip ci]`: el commit vacío no tiene nada que probar; el CI corre cuando el implementador sube el trabajo."""
    return f"Inicia {rama} [skip ci]"


def cuerpo_de_fusion(cuerpo_del_pr):
    """El cuerpo del commit squash. Sin él, GitHub copia los mensajes de los commits, y el `[skip ci]` de la rama
    vacía saltaría el CI de main."""
    cuerpo = (cuerpo_del_pr or "").replace("[skip ci]", "").strip()
    return cuerpo or CUERPO_FUSION


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


def comentarios_rest(numero):
    """Los comentarios del PR con id, fecha y reacciones (`gh pr view` no trae reacciones)."""
    return gh_json("api", f"repos/{repo()}/issues/{numero}/comments?per_page=100")


def marcar_tomado(numero, cuerpo):
    """👀 en el pedido que toma el implementador: `vigilar` distingue un pedido sin tomar de uno en curso."""
    for comentario in reversed(comentarios_rest(numero)):
        if comentario["body"].strip() == cuerpo.strip():
            gh("api", f"repos/{repo()}/issues/comments/{comentario['id']}/reactions", "-f", "content=eyes")
            return


def notificar(titulo, texto, enlace=None):
    """Avisa al dueño en el celular: los comentarios de la cadena salen con su token y GitHub no se los notifica.

    NOTIFICAR_URL es un tema de ntfy (https://ntfy.sh/<tema-secreto>); sin ella el aviso solo queda en Actions.
    """
    print(f"Aviso: {titulo}. {texto}")
    url = os.environ.get("NOTIFICAR_URL")
    if not url:
        return
    pedido = urllib.request.Request(url, data=f"{titulo}\n{texto}".encode(), method="POST")
    if enlace:
        pedido.add_header("Click", enlace)
    try:
        urllib.request.urlopen(pedido, timeout=10)
    except OSError as error:  # un aviso perdido no debe frenar la cadena
        print(f"No pude avisar: {error}")


def url_del_pr(numero):
    return f"https://github.com/{repo()}/pull/{numero}"


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
        f"message={mensaje_rama_vacia(rama)}",
        "-f",
        f"tree={arbol}",
        "-f",
        f"parents[]={base}",
    )["sha"]
    gh("api", f"repos/{repo()}/git/refs", "-f", f"ref=refs/heads/{rama}", "-f", f"sha={commit}")


def pedir_correccion(numero, motivo, origen, comentarios=None):
    """Le pide a Codex que corrija, con un tope de intentos por PR y por origen."""
    comentarios = comentarios_del_pr(numero) if comentarios is None else comentarios
    tope = MAX_CORRECCIONES[origen]
    if correcciones_pedidas(comentarios, origen) >= tope:
        etiquetar(numero, agregar=["bloqueado"])
        comentar(numero, f"Codex agotó {tope} correcciones por {ORIGENES[origen]}: queda `bloqueado` para el dueño.")
        return
    comentar(numero, prompt_corregir(motivo, origen))


def estado_de_fusion(numero, intentos=6):
    """`mergeable` y el último commit del PR. Tras una fusión en main, GitHub responde UNKNOWN mientras recalcula."""
    for _ in range(intentos):
        datos = gh_json("pr", "view", str(numero), "--json", "mergeable,headRefOid")
        if datos["mergeable"] != "UNKNOWN":
            break
        time.sleep(10)
    return datos


def descartar_pedidos_de_opus(numero):
    """Descarta los pedidos de cambios que Opus ya dio por atendidos al poner `revisado:opus`."""
    paginas = gh_json("api", f"repos/{repo()}/issues/{numero}/events?per_page=100", "--paginate", "--slurp")
    aprobacion = aprobacion_de_opus([e for pagina in paginas for e in pagina])
    revisiones = gh_json("api", f"repos/{repo()}/pulls/{numero}/reviews?per_page=100")
    for revision_vieja in revisiones_a_descartar(revisiones, aprobacion):
        mensaje = f"Superada: {aprobacion['actor']['login']} puso revisado:opus el {aprobacion['created_at']}."
        gh(
            "api",
            "--method",
            "PUT",
            f"repos/{repo()}/pulls/{numero}/reviews/{revision_vieja['id']}/dismissals",
            "-f",
            f"message={mensaje}",
        )
        print(f"Descartado el pedido de cambios {revision_vieja['id']} de Opus en el PR #{numero}.")


def pedir_resolver_conflicto(pr):
    """Con dos PR en curso, fusionar uno puede dejar al otro en conflicto, y así no corre su CI ni se fusiona."""
    if "bloqueado" in etiquetas_de(pr):
        return
    datos = estado_de_fusion(pr["number"])
    if datos["mergeable"] != "CONFLICTING":
        return
    marca = MARCA_CONFLICTO.format(sha=datos["headRefOid"])
    comentarios = comentarios_del_pr(pr["number"])
    if any(marca in c for c in comentarios):
        return  # ya pedido para este commit: se espera al implementador
    motivo = f"{marca}\nla rama tiene conflictos con main: integrá main y resolvelos."
    pedir_correccion(pr["number"], motivo, "conflicto", comentarios)
    print(f"PR #{pr['number']} en conflicto con main: pedida la corrección.")


# --- Pasos -----------------------------------------------------------------


ETIQUETAS_DE_ESTADO = ("estado:listo", "estado:en-curso", "estado:revision")


def etiquetas_de_estado_a_quitar(etiquetas):
    """Un issue cerrado ya no está listo, en curso ni en revisión: esas etiquetas confunden al leer el tablero."""
    return [e for e in ETIQUETAS_DE_ESTADO if e in etiquetas]


def limpiar_issues_cerrados():
    """Quita las etiquetas de estado de los issues cerrados (GitHub cierra el issue con `Closes #N` y no las toca)."""
    cerrados = gh_json("issue", "list", "--state", "closed", "--limit", "100", "--json", "number,labels")
    for issue in cerrados:
        sobran = etiquetas_de_estado_a_quitar({e["name"] for e in issue["labels"]})
        if sobran:
            etiquetar(issue["number"], quitar=sobran, tipo="issue")
            print(f"Issue #{issue['number']} cerrado: quité {', '.join(sobran)}.")


def arrancar():
    """Reanuda los PR cuya duda resolvió Opus, pide resolver los conflictos con main y lanza issues hasta el tope."""
    limpiar_issues_cerrados()
    en_curso = {}
    for pr in prs_de_codex():
        numero_issue = numero_de_rama(pr["headRefName"])
        issue = gh_json("issue", "view", str(numero_issue), "--json", "number,title,body,labels")
        en_curso[numero_issue] = etiquetas_de(issue)
        if "estado:listo" in etiquetas_de(issue):
            etiquetar(numero_issue, agregar=["estado:en-curso", "agente:codex"], quitar=["estado:listo"], tipo="issue")
            comentar(
                pr["number"],
                f"{encabezado_de_pedido()} Opus resolvió la duda en el issue: leé su comentario y seguí.\n\n"
                + prompt_implementar(issue),
            )
            print(f"Reanudado el PR #{pr['number']}.")
        elif "necesita-criterio" not in etiquetas_de(issue):
            pedir_resolver_conflicto(pr)
    if len(en_curso) >= MAX_EN_CURSO:
        print(f"Ya hay {len(en_curso)} issues en curso (tope {MAX_EN_CURSO}).")
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
        "number,title,body,labels",
        "--limit",
        "100",
    )
    listos = [i for i in listos if i["number"] not in en_curso]
    issue = elegir_siguiente(listos, esta_cerrado, en_curso.values())
    if issue is None:
        print("No hay issues listos con las dependencias cerradas que no choquen con los en curso.")
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
        f"Closes #{issue['number']}\n\nPR abierto por la cadena (scripts/cadena.py); lo implementa Codex.",
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
        pedir_correccion(numero, "el CI falló: leé el resumen del CI en este PR y arreglalo.", "ci")
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
        pedir_correccion(numero, "corregí los hallazgos de tu revisión.", "revision")


def etiqueta(numero, nombre):
    """Reacciona a una etiqueta nueva en un PR de Codex: avisar un bloqueo, fusionar o corregir lo que pidió Opus."""
    if nombre == "bloqueado":
        notificar(f"PR #{numero} bloqueado", "La cadena lo frenó: necesita al dueño.", url_del_pr(numero))
        return
    pr = next((p for p in prs_de_codex() if p["number"] == numero), None)
    if pr is None or "bloqueado" in etiquetas_de(pr):
        return
    if nombre == "correccion-pendiente" and "revisado:codex" in etiquetas_de(pr):
        pedir_correccion(numero, "atendé la revisión de Opus que está en este PR.", "opus")
        return
    if lista_para_fusionar(etiquetas_de(pr), archivos_del_pr(numero)):
        # Una revisión pedida a mano puede llegar con el PR aún en borrador; GitHub no fusiona borradores.
        gh("pr", "ready", str(numero))
        if "revisado:opus" in etiquetas_de(pr):
            descartar_pedidos_de_opus(numero)
        gh("pr", "merge", str(numero), "--squash", "--auto", "--delete-branch", "--body", cuerpo_de_fusion(pr["body"]))
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


def vigilar(ahora=None):
    """Corre cada 15 minutos: avisa si un pedido no lo toma nadie (implementador apagado) o no termina (colgado)."""
    ahora = ahora or datetime.now(UTC)
    pendientes = [
        (pr, pedido_en_espera(comentarios_rest(pr["number"])))
        for pr in prs_de_codex()
        if "bloqueado" not in etiquetas_de(pr)
    ]
    ocupado = any(pedido and tomado(pedido) for _, pedido in pendientes)
    for pr, pedido in pendientes:
        tipo = demora(pedido, ahora, ocupado)
        if tipo == "sin-tomar":
            texto = f"Nadie tomó el pedido en {SIN_TOMAR_MINUTOS} minutos: ¿está corriendo el implementador?"
        elif tipo == "colgado":
            texto = (
                f"El implementador tomó el pedido y no terminó en {COLGADO_MINUTOS} minutos: ¿Codex sin cupo o colgado?"
            )
        else:
            continue
        comentar(pr["number"], f"{MARCA_AVISO}\n{texto}")
        notificar(f"PR #{pr['number']} demorado", texto, url_del_pr(pr["number"]))


def cierre(numero):
    """Al cerrarse el último issue de Codex de una etapa, publica el informe en su issue de cierre y avisa al dueño."""
    issue = gh_json("issue", "view", str(numero), "--json", "milestone,labels")
    etapa = (issue.get("milestone") or {}).get("title")
    if not etapa or "ejecutor:codex" not in etiquetas_de(issue):
        return
    abiertos = gh_json(
        "issue", "list", "--milestone", etapa, "--state", "open", "--label", "ejecutor:codex", "--json", "number"
    )
    if abiertos:
        return
    opus = gh_json(
        "issue", "list", "--milestone", etapa, "--state", "open", "--label", "ejecutor:opus", "--json", "number,title"
    )
    destino = issue_de_cierre(opus)
    if destino is None:
        notificar(f"Terminó {etapa}", "No hay un issue «Cierre de etapa» abierto donde dejar el informe.")
        return
    comentarios = [
        c["body"] for c in gh_json("issue", "view", str(destino["number"]), "--json", "comments")["comments"]
    ]
    if any(MARCA_INFORME in c for c in comentarios):
        return
    import informe_cadena  # solo acá: las pruebas cargan este módulo sin scripts/ en sys.path

    texto = (
        f"{MARCA_INFORME}\nSe cerró el último issue de Codex de «{etapa}». Toca revisar los ADR provisionales "
        f"y cerrar la etapa.\n\n{informe_cadena.informe(etapa)}"
    )
    gh("issue", "comment", str(destino["number"]), "--body", texto)
    notificar(
        f"Terminó {etapa}",
        f"Informe en el issue #{destino['number']}: toca revisar los ADR provisionales.",
        f"https://github.com/{repo()}/issues/{destino['number']}",
    )


def main(argv=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    pasos = analizador.add_subparsers(dest="paso", required=True)
    pasos.add_parser("arrancar")
    pasos.add_parser("vigilar")
    pasos.add_parser("cierre").add_argument("--issue", type=int, required=True)
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
    elif args.paso == "vigilar":
        vigilar()
    elif args.paso == "cierre":
        cierre(args.issue)
    elif args.paso == "fusionar-adr":
        fusionar_adr(args.rama)
    else:
        etiqueta(args.pr, args.etiqueta)


if __name__ == "__main__":
    sys.exit(main())
