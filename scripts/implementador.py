"""Implementador local: hace en esta PC lo que Codex cloud no responde desde GitHub (ver docs/protocolo-agentes.md).

La cadena (scripts/cadena.py) sigue abriendo el PR borrador y comentando el pedido de implementar o corregir
(con la marca `<!-- cadena:pedido -->` o `<!-- cadena:corregir -->`, sin mencionar a `@codex`).
Este script toma el último pedido de esos comentarios que nadie atendió, corre `codex exec`
en un worktree de la rama del PR, sube el resultado y deja un comentario con la marca de «hecho».
El CI, la revisión y la fusión siguen a cargo de la cadena.

Uso:
  python scripts/implementador.py            # atiende los pedidos pendientes y termina
  python scripts/implementador.py --esperar  # repite cada 60 segundos hasta Ctrl+C
  python scripts/implementador.py --pr 150   # atiende solo ese PR
  python scripts/implementador.py --simular  # dice qué haría, sin tocar nada
  python scripts/implementador.py --estado   # en qué paso está cada PR de Codex y qué espera

Todo lo que muestra también queda en `.implementador/registro.log`; la salida completa de Codex, en
`.implementador/codex-crudo.log` (con GIMNASIO_IMPL_VERBOSO=1 se muestra entera). Solo corre una instancia a la vez.
"""

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path, PurePosixPath

import cadena
import verificar_cache_pwa

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_TRABAJO = RAIZ / ".implementador"
REGISTRO = CARPETA_TRABAJO / "registro.log"
BLOQUEO = CARPETA_TRABAJO / "bloqueo.pid"
CRUDO = CARPETA_TRABAJO / "codex-crudo.log"  # la salida completa de Codex; en pantalla va resumida
SONDEO_SEGUNDOS = 30  # cada cuánto se revisa si Codex sigue dando señales
INACTIVIDAD_AVISO_MINUTOS = 10  # sin una línea nueva de Codex: se avisa
INACTIVIDAD_CORTE_MINUTOS = 20  # sin una línea nueva de Codex: se lo mata y cuenta como fallo del pedido
CUENTA_REGRESIVA_SEGUNDOS = 5 * 60
LIMITE_PRUEBAS_MINUTOS = 20
SERVICE_WORKER = verificar_cache_pwa.SERVICE_WORKER
MAPA_CAPACIDADES = "docs/MAPA-CAPACIDADES.md"
VERSION_SW = re.compile(r'(const VERSION = ")(\d+)(")')
CONFLICTO = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.DOTALL)
SESION = {
    "inicio": time.time(),
    "atendidos": [],
    "fallos": [],
    "sin_cupo": 0,
    "sin_borrar": set(),
    "codex_sin_cupo_hasta": 0.0,  # mientras dure, implementa el respaldo en vez de esperar a Codex
    "reintentar_desde": {},  # PR que acaba de fallar → cuándo se reintenta; mientras tanto se atienden los demás
}
MARCA_HECHO = cadena.MARCA_HECHO
MARCA_FALLO = cadena.MARCA_FALLO
MAX_FALLOS = 3
ESPERA_REINTENTO_SEGUNDOS = 10 * 60  # un fallo pasajero se cura solo: el PR se bloquea recién tras varios intentos
LIMITE_MINUTOS = 60
ESPERA_SEGUNDOS = 60
LIMITE_REVISIONES = 20000
ARCHIVO_CUERPO = ".implementador-cuerpo.md"
ESPERA_CUPO_SEGUNDOS = 15 * 60
ESFUERZO_POR_DEFECTO = "low"  # el cupo de Codex rinde más; GIMNASIO_CODEX_ESFUERZO lo cambia (low|medium|high)
ESCALA_ESFUERZO = ("low", "medium", "high")
RESPALDO_POR_DEFECTO = "sonnet"  # modelo de Claude que implementa sin cupo de Codex; GIMNASIO_RESPALDO=ninguno lo apaga
MARCAS_SIN_CUPO = (
    "hit your usage limit",
    "hit your limit",
    "usage limit reached",
    "5-hour limit",  # Claude: «You've hit your 5-hour limit · resets 6pm»
    "weekly limit",
)
# En Windows la herramienta de shell de Claude Code es PowerShell; en Linux, Bash: las reglas cubren las dos.
_CONSULTAS = ("python", "pytest", "ruff", "node", "git status", "git diff", "git log", "git show", "ls")
_VEDADOS = ("git push", "gh", "curl", "Invoke-WebRequest", "Invoke-RestMethod")
HERRAMIENTAS_PERMITIDAS = "Read Edit Write Glob Grep " + " ".join(
    f"{shell}({comando}:*)" for shell in ("Bash", "PowerShell") for comando in _CONSULTAS
)
HERRAMIENTAS_PROHIBIDAS = (
    " ".join(f"{shell}({comando}:*)" for shell in ("Bash", "PowerShell") for comando in _VEDADOS)
    + " WebFetch WebSearch"
)
PEDIDO = re.compile(r"^\s*@codex\s+(?!review\b)\S", re.IGNORECASE)
# Claude Code niega en `-p` la ruta completa al .venv, `Invoke-Expression`, `$env:` y `cd`: son las formas de AGENTS.md.
INSTRUCCIONES_RESPALDO = (
    "En esta corrida los comandos permitidos son `python`, `pytest`, `ruff`, `node` y `git` de solo lectura. "
    "Ya salen del .venv y `GIMNASIO_BD_*` ya está definida. Corré uno por llamada, sin ruta, y sin `.venv`, "
    "`Invoke-Expression`, `$env:` ni `cd`, aunque AGENTS.md los muestre: se niegan. Si un comando se niega, "
    "seguí con el pedido: el implementador verifica antes de subir y el CI es la puerta.\n\n"
)


class SinCupo(RuntimeError):
    """Codex se quedó sin cupo de uso: no es un fallo del pedido, hay que esperar a que se renueve."""


# --- Lógica pura -----------------------------------------------------------


def es_falta_de_cupo(texto):
    minusculas = (texto or "").lower()
    return any(marca in minusculas for marca in MARCAS_SIN_CUPO)


def respaldo():
    """El modelo de Claude que implementa mientras Codex no tiene cupo, o None si el respaldo está apagado."""
    modelo = (os.environ.get("GIMNASIO_RESPALDO") or RESPALDO_POR_DEFECTO).strip().lower()
    return None if modelo in ("ninguno", "no", "off") else modelo


def motor_para_ahora(ahora, sin_cupo_hasta, modelo_respaldo):
    """«codex», o el modelo de respaldo mientras dure la espera de cupo de Codex."""
    return modelo_respaldo if modelo_respaldo and ahora < sin_cupo_hasta else "codex"


def resultado_de_claude(salida):
    """(texto final, tokens, con_error) de la salida `stream-json` de `claude -p`; el último `result` manda."""
    texto, tokens, con_error = "", 0, False
    for linea in (salida or "").splitlines():
        try:
            dato = json.loads(linea)
        except ValueError:
            continue
        if isinstance(dato, dict) and dato.get("type") == "result":
            uso = dato.get("usage") or {}
            texto = str(dato.get("result") or "")
            tokens = sum(int(uso.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens"))
            con_error = bool(dato.get("is_error"))
    return texto, tokens, con_error


def es_pedido(cuerpo):
    """Un comentario de la cadena que le pide trabajo a Codex (no la revisión, que sí responde en la nube)."""
    cuerpo = cuerpo or ""
    if cadena.MARCA_PEDIDO in cuerpo or cadena.MARCA_CORREGIR in cuerpo:
        return True
    return bool(PEDIDO.match(re.sub(r"<!--.*?-->", "", cuerpo, flags=re.DOTALL)))  # pedidos con @codex, de antes


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


def texto_de_revisiones(resenas, en_linea, desde):
    """Lo que dijeron los revisores después de `desde` (fecha ISO del último «hecho»), para que Codex lo lea.

    Codex solo recibe el texto del pedido; sin esto no vería los hallazgos, que viven en las revisiones del PR.
    """
    partes = []
    for r in resenas:
        if (r.get("submitted_at") or "") > desde and r["body"].strip() and "codex-review-receipt" not in r["body"]:
            partes.append(f"Revisión de {r['user']['login']}:\n{r['body'].strip()}")
    for c in en_linea:
        if c["created_at"] > desde:
            partes.append(
                f"Comentario de {c['user']['login']} en {c['path']}:{c.get('line') or '?'}:\n{c['body'].strip()}"
            )
    return "\n\n".join(partes)[:LIMITE_REVISIONES]


def cuerpo_del_pr(texto, numero_issue):
    """El cuerpo que dejó Codex, con `Closes #N` al principio como exige AGENTS.md; None si no dejó nada."""
    texto = (texto or "").strip()
    if not texto:
        return None
    return texto if texto.startswith("Closes #") else f"Closes #{numero_issue}\n\n{texto}"


def prompt_para_codex(pedido, revisiones=""):
    texto = re.sub(r"<!--.*?-->", "", pedido, flags=re.DOTALL).strip()
    texto = texto.removeprefix("@codex").removeprefix(cadena.ENCABEZADO_LOCAL).strip()
    encabezado = (
        "Trabajás en un worktree de la rama de este PR. No hagas commit ni push: lo hace el implementador.\n"
        "Si la rama tiene conflictos con main sin resolver, resolvelos preservando el alcance del issue.\n"
        "Escribí el cuerpo del PR (plantilla completa, con «Notas para el próximo agente» y lo que no pudiste correr) "
        f"en `{ARCHIVO_CUERPO}` en la raíz: lo publica el implementador (sin `gh`).\n"
        "Para ahorrar tiempo y cupo: corré ruff y `node --test`; no corras pytest sobre varios archivos: "
        "el implementador corre las pruebas de los módulos que tocás (con MySQL) al terminar y te devuelve los fallos. "
        "En el cuerpo escribí «pruebas de Python: las corre el implementador»; passed/skipped lo da el CI. "
        "Corré pytest solo si necesitás diagnosticar un fallo puntual, y apuntá a un archivo. "
        "La suite completa y los e2e los corre el CI: corré un e2e solo para diagnosticar uno que el CI marcó en rojo. "
        "No lances revisiones aparte: las hace la cadena.\n"
        "Lista de control: si tocás algo de `gimnasio/static/` que no sea una prueba, subí `VERSION` en "
        "`gimnasio/static/sw.js` (si no, los navegadores con el service worker viejo no reciben el cambio); "
        "el implementador lo verifica antes de subir y el CI lo exige.\n"
        "Si te falta una decisión, una duda solo se reconoce si una línea empieza exactamente con "
        f"`{cadena.PEDIDO_CRITERIO}`, sin adornos antes. Decirla de otro modo no sirve: terminar sin cambios "
        "en la rama y sin esa línea cuenta como fallo del pedido, aunque dejes el cuerpo del PR.\n\n"
    )
    detalle = f"\n\n--- Revisiones del PR a atender ---\n{revisiones}" if revisiones else ""
    return encabezado + texto + detalle


def prompt_de_verificacion(informe, archivos=()):
    """El pedido de arreglar lo que la verificación encontró, antes de gastar una vuelta del CI."""
    return (
        "Trabajás en un worktree de la rama de este PR. No hagas commit ni push: lo hace el implementador.\n"
        "La verificación previa a subir falló. Arreglá solo esto, sin salirte del alcance del issue, "
        f"y no toques `{ARCHIVO_CUERPO}`.\n"
        "Ya tenés el contexto: abrí solo los archivos de abajo y los de las pruebas que fallan; no releas AGENTS.md, "
        "VISION.md, el glosario ni las skills, ni corras la suite completa.\n"
        f"Archivos que cambiaste en este intento: {', '.join(archivos) or 'ninguno'}.\n\n" + "\n".join(informe)
    )


LINEAS_DE_FALLO = 25
INDICIO_DE_FALLO = re.compile(r"^(FAILED|ERROR)\b|^E\s|Error|assert|Timeout|Expected|Locator|\.py:\d+")
RUIDO_DE_SERVIDOR = re.compile(r"^(INFO|DEBUG|WARNING)\s+\w+:|werkzeug|^\s*$")


def resumen_de_fallo(salida, limite=LINEAS_DE_FALLO):
    """Las líneas de la salida de pytest que dicen qué falló, sin el ruido del servidor; la cola si no hay indicios."""
    lineas = [linea.rstrip() for linea in (salida or "").splitlines() if not RUIDO_DE_SERVIDOR.search(linea)]
    indicios = [linea for linea in lineas if INDICIO_DE_FALLO.search(linea)]
    return "\n".join((indicios or lineas)[-limite:])


def tokens_de(salida):
    """Los tokens que informa `codex exec` al final («tokens used» y la cifra en la línea siguiente); 0 si no está."""
    cifras = re.findall(r"tokens used\s*\n\s*([\d.,]+)", salida or "")
    return int(re.sub(r"\D", "", cifras[-1])) if cifras else 0


def tests_a_correr(archivos, existentes):
    """Las pruebas de `pruebas/` que corresponden a lo cambiado: las tocadas y las del módulo `gimnasio/<módulo>/`."""
    elegidas = set()
    for archivo in archivos:
        partes = PurePosixPath(archivo).parts
        if archivo in existentes:
            elegidas.add(archivo)
        elif len(partes) >= 3 and partes[0] == "gimnasio":
            elegidas.update(t for t in existentes if PurePosixPath(t).name.startswith(f"test_{partes[1]}"))
    return sorted(elegidas)


def contar_pruebas(salida):
    """Cuenta de la última línea de resumen de pytest, por ejemplo {'passed': 67, 'failed': 1}."""
    for linea in reversed((salida or "").splitlines()):
        cuentas = re.findall(r"(\d+) (passed|failed|skipped|errors?)\b", linea)
        if cuentas and " in " in linea:
            return {("error" if palabra.startswith("error") else palabra): int(n) for n, palabra in cuentas}
    return {}


def nombres_de_prueba_repetidos(archivos):
    """Archivos `test_*.py` que comparten nombre en carpetas distintas: pytest no los recolecta juntos."""
    por_nombre = {}
    for archivo in archivos:
        por_nombre.setdefault(PurePosixPath(archivo).name, []).append(archivo)
    return {nombre: sorted(rutas) for nombre, rutas in por_nombre.items() if len(rutas) > 1}


def necesita_subir_cache(archivos):
    """Tocar recursos de la PWA sin subir VERSION deja a los navegadores con el service worker viejo."""
    return verificar_cache_pwa.toca_recursos_pwa(archivos) and SERVICE_WORKER not in archivos


def subir_version_sw(codigo):
    """El código del service worker con VERSION + 1; None si no encuentra la constante."""
    if not VERSION_SW.search(codigo):
        return None
    return VERSION_SW.sub(lambda m: f"{m[1]}{int(m[2]) + 1}{m[3]}", codigo, count=1)


def resolver_version_sw(codigo):
    """`sw.js` con los conflictos que son solo de VERSION resueltos en la mayor + 1; los demás quedan como están."""

    def resolver(conflicto):
        ours, theirs = conflicto[1].strip(), conflicto[2].strip()
        version = re.compile(r'const VERSION = "(\d+)";?')
        (uno, otro) = version.fullmatch(ours), version.fullmatch(theirs)
        if not (uno and otro):
            return conflicto[0]
        return VERSION_SW.sub(lambda m: f"{m[1]}{max(int(uno[1]), int(otro[1])) + 1}{m[3]}", conflicto[1])

    return CONFLICTO.sub(resolver, codigo)


def etapa_del_pr(etiquetas, hay_pedido, checks, sensible, parada=False):
    """En qué paso de la cadena está un PR de Codex y qué espera. `checks` son los de statusCheckRollup.

    `parada`: la corrección pendiente ya se pidió y su pedido se cerró sin commit (ver cadena.correccion_parada).
    """
    estados = [(c.get("conclusion") or c.get("state") or "").upper() for c in checks]
    en_curso = any(c.get("status") not in (None, "COMPLETED") for c in checks) or "PENDING" in estados
    rojo = any(e in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE") for e in estados)
    if "bloqueado" in etiquetas:
        return "bloqueado: lo desbloquea el dueño"
    if hay_pedido:
        return "pedido pendiente: lo atiende el implementador"
    if en_curso:
        return "esperando el CI"
    if parada:
        return "corrección parada: su pedido se cerró sin commit y nadie la va a volver a pedir; le toca al dueño"
    if rojo:
        return "CI en rojo: la cadena va a pedir una corrección"
    if "correccion-pendiente" in etiquetas:
        return "corrección pendiente: la cadena la va a pedir"
    if "revisado:codex" not in etiquetas:
        return "esperando la revisión de Codex"
    if sensible and "revisado:opus" not in etiquetas:
        return "esperando la revisión de Opus (ruta sensible)"
    return "lista: la fusión automática debería ocurrir"


class ResumenDeCodex:
    """Reduce la salida de `codex exec` a lo que Codex hace, línea a línea.

    `codex exec` imprime bloques que empiezan con una marca (`user`, `codex`, `exec`, `apply patch`, `tokens used`):
    el prompt entero, cada archivo que lee y cada diff. Aquí queda una línea por mensaje, comando y parche,
    y de un comando que falla, las primeras líneas de su salida. Lo crudo va a `CRUDO`.
    """

    MARCAS = {"user", "codex", "exec", "apply patch", "file update", "thinking", "tokens used"}
    COMANDO = re.compile(r'^"[^"]*powershell\.exe" -Command ')
    CARPETA_AL_FINAL = re.compile(r" in [A-Za-z]:\\.*$")
    RESULTADO = re.compile(r"^\s*(succeeded|exited (\d+)) in ([\d.]+m?s):")
    CARPETA_DE_ISSUE = re.compile(r"issue-\d+(?:-\d+)?[\\/](.*)$")
    ANCHO = 150
    LINEAS_DE_ERROR = 2

    def __init__(self):
        self.bloque = "encabezado"
        self.linea_del_bloque = 0
        self.errores_por_mostrar = 0

    def _corto(self, texto):
        texto = " ".join(texto.split())
        return texto if len(texto) <= self.ANCHO else texto[: self.ANCHO - 1] + "…"

    def procesar(self, linea):
        """Las líneas a mostrar para esta línea cruda de Codex (casi siempre ninguna)."""
        texto = linea.rstrip()
        if texto.strip() in self.MARCAS:
            self.bloque, self.linea_del_bloque, self.errores_por_mostrar = texto.strip(), 0, 0
            return []
        self.linea_del_bloque += 1
        if self.bloque == "encabezado":
            clave = texto.split(":", 1)[0]
            return [texto] if clave in ("model", "reasoning effort") else []
        if self.bloque == "codex" and self.linea_del_bloque == 1:
            return [f"💬 {self._corto(texto)}"]
        if self.bloque == "tokens used" and self.linea_del_bloque == 1:
            return [f"tokens: {texto.strip()}"]
        if self.bloque == "exec":
            return self._exec(texto)
        if self.bloque == "apply patch":
            return self._parche(texto)
        return []

    def _exec(self, texto):
        if self.linea_del_bloque == 1:
            comando = self.CARPETA_AL_FINAL.sub("", self.COMANDO.sub("", texto))
            return [f"$ {self._corto(comando)}"]
        if (resultado := self.RESULTADO.match(texto)) is not None:
            if resultado[2] in (None, "0"):
                return [f"  ✓ {resultado[3]}"]
            self.errores_por_mostrar = self.LINEAS_DE_ERROR
            return [f"  ✗ código {resultado[2]} ({resultado[3]})"]
        if self.errores_por_mostrar and texto.strip():
            self.errores_por_mostrar -= 1
            return [f"    {self._corto(texto)}"]
        return []

    def _parche(self, texto):
        if texto.startswith("diff --git"):
            self.bloque = "diff"  # el resto del bloque es el diff: no se muestra
            return []
        if self.linea_del_bloque == 1 or not texto.strip():  # «patch: completed»
            return []
        encontrado = self.CARPETA_DE_ISSUE.search(texto)
        return [f"✎ edita {encontrado[1] if encontrado else texto.strip()}"]


class ResumenDeClaude:
    """Una línea por acción de `claude -p --output-format stream-json`: lo que escribe, edita y corre."""

    ANCHO = 150

    def _corto(self, texto):
        texto = " ".join(str(texto).split())
        return texto if len(texto) <= self.ANCHO else texto[: self.ANCHO - 1] + "…"

    def procesar(self, linea):
        try:
            dato = json.loads(linea)
        except ValueError:
            return []
        if not isinstance(dato, dict):
            return []
        if dato.get("type") == "system" and dato.get("subtype") == "init":
            return [f"model: {dato.get('model', '?')}"]
        if dato.get("type") != "assistant":
            return []
        visibles = []
        for bloque in (dato.get("message") or {}).get("content") or []:
            if bloque.get("type") == "text" and bloque.get("text", "").strip():
                visibles.append(f"💬 {self._corto(bloque['text'])}")
            elif bloque.get("type") == "tool_use":
                entrada = bloque.get("input") or {}
                if bloque.get("name") in ("Edit", "Write"):
                    ruta = ResumenDeCodex.CARPETA_DE_ISSUE.search(str(entrada.get("file_path", "")))
                    visibles.append(f"✎ edita {ruta[1] if ruta else entrada.get('file_path', '?')}")
                elif bloque.get("name") in ("Bash", "PowerShell"):
                    visibles.append(f"$ {self._corto(entrada.get('command', ''))}")
        return visibles


def formatear_resumen(sesion, fusionados, ahora):
    """El resumen de lo que hizo esta corrida del implementador, para la consola y el registro."""
    atendidos = sesion["atendidos"]
    lineas = [f"Resumen de la corrida ({(ahora - sesion['inicio']) / 60:.0f} min en marcha):"]
    for a in atendidos:
        lineas.append(f"  · PR #{a['pr']}: {a['resultado']} en {a['minutos']:.1f} min, {a['tokens']:,} tokens")
    lineas.append(
        f"  Atendidos: {len(atendidos)} · Fallos: {len(sesion['fallos'])} · Veces sin cupo: {sesion['sin_cupo']}"
    )
    motores = dict.fromkeys(a.get("motor", "codex") for a in atendidos)
    for motor in motores or ["codex"]:
        propios = [a for a in atendidos if a.get("motor", "codex") == motor]
        minutos, tokens = sum(a["minutos"] for a in propios), sum(a["tokens"] for a in propios)
        lineas.append(f"  {motor.capitalize()}: {minutos:.1f} min y {tokens:,} tokens en total")
    if fusionados:
        lineas.append("  Fusionados desde que arrancó: " + ", ".join(f"#{n}" for n in fusionados))
    return "\n".join(lineas)


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


def binario_claude():
    """El ejecutable nativo de Claude Code, o None. Se prefiere `claude.exe` a `claude.cmd`: los argumentos con
    paréntesis y comodines no sobreviven a cmd.exe."""
    if os.environ.get("GIMNASIO_CLAUDE_BIN"):
        return os.environ["GIMNASIO_CLAUDE_BIN"]
    datos = os.environ.get("APPDATA")
    if datos:
        nativo = Path(datos) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if nativo.exists():
            return str(nativo)
    return shutil.which("claude")


def git(*argumentos, cwd=RAIZ, chequear=True):
    resultado = subprocess.run(
        ["git", *argumentos], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if chequear and resultado.returncode != 0:
        raise RuntimeError(f"git {' '.join(argumentos)}: {resultado.stderr.strip()}")
    return resultado


def preparar_worktree(rama, numero):
    git("fetch", "origin", "--prune")
    carpeta = CARPETA_TRABAJO / f"issue-{numero}"
    for intento in range(1, 10):
        if carpeta.exists():
            git("worktree", "remove", "--force", str(carpeta), chequear=False)
            shutil.rmtree(carpeta, ignore_errors=True)
        if not carpeta.exists():
            break
        # El sandbox de Codex a veces deja carpetas (.pytest_cache) que el usuario no puede borrar: se usa otra.
        carpeta = CARPETA_TRABAJO / f"issue-{numero}-{intento}"
    git("worktree", "prune")
    git("worktree", "add", "-B", rama, str(carpeta), f"origin/{rama}")
    # Los conflictos previsibles se resuelven aquí; los demás quedan en el árbol para que Codex los resuelva.
    git("merge", "origin/main", "--no-edit", cwd=carpeta, chequear=False)
    if resueltos := resolver_conflictos_previsibles(carpeta):
        paso("Conflictos resueltos sin agente: " + ", ".join(resueltos))
    return carpeta


def archivos_en_conflicto(carpeta):
    return git("diff", "--name-only", "--diff-filter=U", cwd=carpeta).stdout.split()


def resolver_conflictos_previsibles(carpeta):
    """VERSION de `sw.js` y el mapa generado no necesitan a un agente. Devuelve los archivos que resolvió."""
    conflictos, resueltos = archivos_en_conflicto(carpeta), []
    if SERVICE_WORKER in conflictos:
        sw = carpeta / SERVICE_WORKER
        codigo = resolver_version_sw(sw.read_text(encoding="utf-8"))
        if not CONFLICTO.search(codigo):
            sw.write_text(codigo, encoding="utf-8", newline="\n")
            resueltos.append(SERVICE_WORKER)
    fichas_sanas = not any(a.startswith("docs/capacidades/") for a in conflictos)
    regenerar = [python_del_proyecto(), "scripts/mapa_capacidades.py"]
    if MAPA_CAPACIDADES in conflictos and fichas_sanas and correr(regenerar, carpeta, 2)[0] == 0:
        resueltos.append(MAPA_CAPACIDADES)
    if resueltos:
        git("add", *resueltos, cwd=carpeta)
    return resueltos


def carpetas_sobrantes(nombres, abiertos):
    """Las carpetas de trabajo (`issue-N` y los reintentos `issue-N-k`) de issues sin PR abierto."""
    sobran = []
    for nombre in nombres:
        encontrado = re.fullmatch(r"issue-(\d+)(-\d+)?", nombre)
        if encontrado and int(encontrado[1]) not in abiertos:
            sobran.append(nombre)
    return sorted(sobran)


def medida_de_codex(minutos, tokens, nivel):
    """Marca oculta en el comentario «hecho»: la suma `scripts/informe_cadena.py` al informe de la etapa."""
    return f"<!-- implementador:codex minutos={minutos:.1f} tokens={tokens} esfuerzo={nivel} -->"


def esfuerzo(fallos=0, previas=0):
    """Bajo para que rinda el cupo; un nivel más por cada fallo del pedido o corrección repetida del mismo origen."""
    base = os.environ.get("GIMNASIO_CODEX_ESFUERZO") or ESFUERZO_POR_DEFECTO
    if base not in ESCALA_ESFUERZO:
        return base
    indice = min(ESCALA_ESFUERZO.index(base) + fallos + previas, len(ESCALA_ESFUERZO) - 1)
    return ESCALA_ESFUERZO[indice]


def correcciones_previas(pedido, comentarios):
    """Cuántas veces antes se pidió una corrección del mismo origen que `pedido` (0 si es de implementar)."""
    origen = cadena.origen_de(pedido)
    return max(cadena.correcciones_pedidas(comentarios, origen) - 1, 0) if origen else 0


def comando_codex(binario, carpeta, salida, nivel=None):
    return [
        binario,
        "exec",
        "-C",
        str(carpeta),
        "-s",
        "workspace-write",
        "-c",
        f'model_reasoning_effort="{nivel or esfuerzo()}"',
    ] + [
        "-o",
        str(salida),
        "-",
    ]


def comando_claude(binario, modelo):
    """`claude -p` con el prompt por stdin: edita y corre lo del proyecto, sin push, `gh` ni red."""
    return [
        binario,
        "-p",
        "--model",
        modelo,
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        HERRAMIENTAS_PERMITIDAS,
        "--disallowedTools",
        HERRAMIENTAS_PROHIBIDAS,
    ]


def medida_del_respaldo(modelo, minutos, tokens):
    """Marca oculta del comentario «hecho» cuando implementó el respaldo en vez de Codex."""
    return f"<!-- implementador:{modelo} minutos={minutos:.1f} tokens={tokens} -->"


def correr_claude(carpeta, prompt, modelo):
    """El respaldo de Codex: `claude -p` en el worktree. Devuelve (código, texto final, tokens) como `correr_codex`."""
    binario = binario_claude()
    if binario is None:
        raise RuntimeError("No encuentro Claude: definí GIMNASIO_CLAUDE_BIN con la ruta de claude.exe.")
    entorno = dict(os.environ)  # el Python del proyecto primero: `python`, `pytest` y `ruff` salen del .venv
    entorno["PATH"] = str(Path(python_del_proyecto()).parent) + os.pathsep + entorno.get("PATH", "")
    proceso = subprocess.Popen(
        comando_claude(binario, modelo),
        cwd=carpeta,
        env=entorno,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    threading.Thread(target=_entregar_prompt, args=(proceso, prompt), daemon=True).start()
    lineas = queue.Queue()
    threading.Thread(target=_leer_lineas, args=(proceso.stdout, lineas), daemon=True).start()
    try:
        registro = _seguir_a_codex(proceso, lineas, ResumenDeClaude, modelo.capitalize())
    finally:
        if proceso.poll() is None:
            proceso.kill()
    codigo = proceso.wait()
    salida = "".join(registro)
    texto, tokens, con_error = resultado_de_claude(salida)
    if (codigo != 0 or con_error) and es_falta_de_cupo(salida):
        raise SinCupo(texto or "Sin cupo de Claude.")
    return codigo or int(con_error), texto or salida[-2000:], tokens


def correr_codex(carpeta, prompt, nivel=None):
    binario = binario_codex()
    if binario is None:
        raise RuntimeError("No encuentro Codex: definí GIMNASIO_CODEX_BIN con la ruta de codex.exe.")
    salida = carpeta / ".implementador-ultimo.txt"
    proceso = subprocess.Popen(
        comando_codex(binario, carpeta, salida, nivel),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # Hilos aparte para no trabarse: uno entrega el prompt y otro lee las líneas, así se puede medir el silencio.
    threading.Thread(target=_entregar_prompt, args=(proceso, prompt), daemon=True).start()
    lineas = queue.Queue()
    threading.Thread(target=_leer_lineas, args=(proceso.stdout, lineas), daemon=True).start()
    try:
        registro = _seguir_a_codex(proceso, lineas)
    finally:
        if proceso.poll() is None:
            proceso.kill()
    codigo = proceso.wait()
    stderr = "".join(registro)
    texto = salida.read_text(encoding="utf-8").strip() if salida.exists() else stderr[-2000:]
    salida.unlink(missing_ok=True)
    if codigo != 0 and es_falta_de_cupo(stderr + texto):
        raise SinCupo(next((linea for linea in stderr.splitlines() if "usage limit" in linea), "Sin cupo de Codex."))
    return codigo, texto, tokens_de(stderr)


def _entregar_prompt(proceso, prompt):
    try:
        proceso.stdin.write(prompt)
        proceso.stdin.close()
    except OSError:
        pass  # Codex cerró antes de leer: el código de salida lo cuenta


def _leer_lineas(flujo, cola):
    for linea in flujo:
        cola.put(linea)
    cola.put(None)


def _seguir_a_codex(proceso, lineas, clase_resumen=None, nombre="Codex"):
    """Muestra lo que dice el implementador; lo corta si pasa el límite total o se queda mudo. Devuelve sus líneas."""
    inicio = ultima_senal = time.monotonic()
    avisado = False
    registro = []
    resumen = None if os.environ.get("GIMNASIO_IMPL_VERBOSO") else (clase_resumen or ResumenDeCodex)()
    CARPETA_TRABAJO.mkdir(exist_ok=True)
    with CRUDO.open("a", encoding="utf-8", newline="\n") as crudo:
        return _vigilar_lineas(proceso, lineas, registro, resumen, crudo, inicio, ultima_senal, avisado, nombre)


def _vigilar_lineas(proceso, lineas, registro, resumen, crudo, inicio, ultima_senal, avisado, nombre="Codex"):
    while True:
        try:
            linea = lineas.get(timeout=SONDEO_SEGUNDOS)
        except queue.Empty:
            linea = ""
        ahora = time.monotonic()
        if linea is None:
            return registro
        if linea:
            registro.append(linea)
            crudo.write(linea if linea.endswith("\n") else linea + "\n")
            crudo.flush()
            for visible in [linea.rstrip()] if resumen is None else resumen.procesar(linea):
                mostrar(f"   │ {visible}")
            ultima_senal, avisado = ahora, False
        mudo = (ahora - ultima_senal) / 60
        if ahora - inicio > LIMITE_MINUTOS * 60:
            proceso.kill()
            raise RuntimeError(f"{nombre} pasó el límite de {LIMITE_MINUTOS} min y se lo cortó.")
        if mudo > INACTIVIDAD_CORTE_MINUTOS:
            proceso.kill()
            raise RuntimeError(f"{nombre} estuvo {INACTIVIDAD_CORTE_MINUTOS} min sin dar señales y se lo cortó.")
        if mudo > INACTIVIDAD_AVISO_MINUTOS and not avisado:
            avisado = True
            paso(f"{nombre} lleva {mudo:.0f} min sin escribir nada; se lo corta a los {INACTIVIDAD_CORTE_MINUTOS}.")
            avisar("Implementador", f"{nombre} lleva rato sin dar señales.")


def mostrar(mensaje):
    print(mensaje, flush=True)
    try:
        CARPETA_TRABAJO.mkdir(exist_ok=True)
        with REGISTRO.open("a", encoding="utf-8", newline="\n") as archivo:
            archivo.write(mensaje + "\n")
    except OSError:
        pass  # el registro es una ayuda: si no se puede escribir, la consola alcanza


def paso(mensaje):
    mostrar(f"[{time.strftime('%H:%M:%S')}] {mensaje}")


def avisar(titulo, mensaje):
    """Pitido y globo de Windows para enterarse sin mirar la ventana; en otros sistemas no hace nada."""
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.MessageBeep()
        guion = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$n=New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
            "$n.ShowBalloonTip(8000,$env:IMPL_TITULO,$env:IMPL_MENSAJE,'Info');Start-Sleep 9;$n.Dispose()"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", guion],
            env={**os.environ, "IMPL_TITULO": titulo, "IMPL_MENSAJE": mensaje},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception:  # noqa: BLE001  el aviso nunca debe tumbar al implementador
        pass


def esperar_con_cuenta(segundos, motivo):
    """Duerme mostrando a qué hora se reintenta y cuánto falta."""
    vuelve = time.strftime("%H:%M", time.localtime(time.time() + segundos))
    paso(f"{motivo}; reintento a las {vuelve}.")
    final = time.monotonic() + segundos
    while (resta := final - time.monotonic()) > 0:
        time.sleep(min(CUENTA_REGRESIVA_SEGUNDOS, resta))
        if (resta := final - time.monotonic()) > 1:
            paso(f"Faltan {resta / 60:.0f} min para reintentar.")


def proceso_vivo(pid):
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.windll.kernel32
        abierto = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not abierto:
            return False
        codigo = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(abierto, ctypes.byref(codigo))
        kernel.CloseHandle(abierto)
        return bool(ok) and codigo.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tomar_bloqueo():
    """Una sola instancia a la vez: dos implementadores atenderían el mismo pedido."""
    CARPETA_TRABAJO.mkdir(exist_ok=True)
    if BLOQUEO.exists():
        texto = BLOQUEO.read_text(encoding="utf-8").strip()
        if texto.isdigit() and int(texto) != os.getpid() and proceso_vivo(int(texto)):
            raise SystemExit(
                f"Ya hay un implementador corriendo (PID {texto}). Si no es así, borrá {BLOQUEO} y reintentá."
            )
    BLOQUEO.write_text(str(os.getpid()), encoding="utf-8", newline="\n")


def soltar_bloqueo():
    if BLOQUEO.exists() and BLOQUEO.read_text(encoding="utf-8").strip() == str(os.getpid()):
        BLOQUEO.unlink(missing_ok=True)


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


def integrar_main(carpeta, rama, titulo):
    """Sube la fusión con main ya resuelta, sin agente; False si la rama no quedó adelante de lo publicado."""
    if git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=carpeta, chequear=False).returncode == 0:
        git("add", "-A", cwd=carpeta)
        git("commit", "-m", titulo, cwd=carpeta)
    if git("rev-list", "--count", f"origin/{rama}..HEAD", cwd=carpeta).stdout.strip() == "0":
        return False
    git("push", "origin", f"HEAD:{rama}", cwd=carpeta)
    return True


def relanzar_ci(carpeta, rama, titulo):
    """Commit vacío: la rama ya tiene el trabajo y solo falta que corran el CI y la revisión."""
    git("commit", "--allow-empty", "-m", titulo, cwd=carpeta)
    git("push", "origin", f"HEAD:{rama}", cwd=carpeta)


# --- Verificación propia ---------------------------------------------------


def python_del_proyecto():
    """El Python del `.venv` del checkout principal (los worktrees no tienen uno propio)."""
    candidato = RAIZ / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    candidato = candidato.with_suffix(".exe") if sys.platform == "win32" else candidato
    return str(candidato) if candidato.exists() else sys.executable


def correr(comando, carpeta, minutos):
    """Corre un comando fuera del sandbox de Codex; devuelve (código, salida). Un tiempo agotado cuenta como fallo."""
    inicio = time.monotonic()
    nombre = " ".join(str(p) for p in comando[1:6])[:90]
    try:
        r = subprocess.run(
            comando, cwd=carpeta, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=minutos * 60,
        )  # fmt: skip
    except subprocess.TimeoutExpired:
        paso(f"⏱ {nombre}: cortado a los {minutos} min")
        return 1, f"Pasaron {minutos} min sin terminar y se lo cortó."
    paso(f"⏱ {nombre}: {time.monotonic() - inicio:.0f} s (código {r.returncode})")
    return r.returncode, (r.stdout + r.stderr).strip()


def archivos_cambiados(carpeta, base="origin/main"):
    """Lo que cambió respecto de `base`, incluidos los archivos nuevos que Codex todavía no agregó.

    `base` es el commit con que arrancó el intento: así una corrección chica no vuelve a correr las pruebas de
    todo el PR (el CI ya las corre).
    """
    cambiados = git("diff", "--name-only", base, cwd=carpeta).stdout.split()
    nuevos = git("ls-files", "--others", "--exclude-standard", cwd=carpeta).stdout.split()
    return sorted(set(cambiados + nuevos) - {ARCHIVO_CUERPO})


def asegurar_cache(carpeta, archivos):
    """Sube VERSION del service worker si Codex tocó recursos de la PWA y no lo hizo; devuelve la línea del informe."""
    if not necesita_subir_cache(archivos):
        return None
    sw = carpeta / SERVICE_WORKER
    nuevo = subir_version_sw(sw.read_text(encoding="utf-8")) if sw.exists() else None
    if nuevo is None:
        return "⚠ Se tocó `gimnasio/static/` pero no encontré `VERSION` en `sw.js`: revisar a mano."
    sw.write_text(nuevo, encoding="utf-8", newline="\n")
    return "Subí `VERSION` en `sw.js`: Codex tocó recursos de la PWA sin hacerlo."


def verificar(carpeta, base="origin/main"):
    """Formato, ruff y las pruebas del módulo tocado, corridos aquí: el sandbox de Codex a veces no puede.

    Devuelve (líneas del informe, True si todo salió bien). Los e2e y la suite completa quedan para el CI, la puerta.
    """
    informe, bien = [], True
    archivos = archivos_cambiados(carpeta, base)
    if (aviso := asegurar_cache(carpeta, archivos_cambiados(carpeta))) is not None:
        informe.append(aviso)
        archivos = archivos_cambiados(carpeta, base)
    python = python_del_proyecto()
    fuentes = [a for a in archivos if a.endswith(".py") and (carpeta / a).exists()]
    if fuentes:
        correr([python, "-m", "ruff", "format", *fuentes], carpeta, 5)
    codigo, salida = correr([python, "-m", "ruff", "check", "."], carpeta, 5)
    informe.append("ruff: " + ("sin observaciones" if codigo == 0 else f"con hallazgos\n{salida[-800:]}"))
    bien = bien and codigo == 0
    todas = [p.relative_to(carpeta).as_posix() for p in (carpeta / "pruebas").rglob("test_*.py")]
    if repetidos := nombres_de_prueba_repetidos(todas):
        detalle = "; ".join(f"`{nombre}` en {', '.join(rutas)}" for nombre, rutas in repetidos.items())
        informe.append(f"⚠ Nombres de prueba repetidos, pytest falla al recolectar: {detalle}. Renombrá uno.")
        bien = False
    existentes = {p for p in todas if PurePosixPath(p).parent.as_posix() == "pruebas"}
    pruebas = tests_a_correr(archivos, existentes)
    if not pruebas:
        informe.append("pytest: sin pruebas asociadas a lo cambiado; las corre el CI.")
    else:
        codigo, salida = correr(
            [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *pruebas], carpeta, LIMITE_PRUEBAS_MINUTOS
        )
        cuenta = contar_pruebas(salida)
        detalle = ", ".join(f"{n} {palabra}" for palabra, n in cuenta.items()) or "sin resumen"
        informe.append(
            f"pytest ({len(pruebas)} archivos): {detalle}" + ("" if codigo == 0 else f"\n{resumen_de_fallo(salida)}")
        )
        if cuenta.get("skipped") and not os.environ.get("GIMNASIO_BD_HOST"):
            informe.append("⚠ Hay pruebas saltadas y no está `GIMNASIO_BD_HOST`: un «skipped» no cuenta como verde.")
        bien = bien and codigo == 0
    return informe, bien


# --- Pasos -----------------------------------------------------------------


def revisiones_pendientes(numero):
    """Revisiones y comentarios en línea del PR posteriores al último «hecho» del implementador."""
    comentarios = cadena.gh_json("pr", "view", str(numero), "--json", "comments")["comments"]
    desde = max((c["createdAt"] for c in comentarios if MARCA_HECHO in c["body"]), default="")
    repo = cadena.repo()
    resenas = cadena.gh_json("api", f"repos/{repo}/pulls/{numero}/reviews")
    en_linea = cadena.gh_json("api", f"repos/{repo}/pulls/{numero}/comments")
    return texto_de_revisiones(resenas, en_linea, desde)


def correr_motor(motor, carpeta, prompt, nivel):
    """(código, texto, tokens) de Codex o, si `motor` es un modelo de Claude, del respaldo."""
    if motor == "codex":
        return correr_codex(carpeta, prompt, nivel)
    return correr_claude(carpeta, INSTRUCCIONES_RESPALDO + prompt, motor)


def corregir_lo_verificado(carpeta, motor, nivel, informe, base="origin/main"):
    """Una vuelta para arreglar lo que falló la verificación. Devuelve (informe, bien, tokens); no pierde lo hecho."""
    paso("La verificación falló: pido la corrección antes de subir…")
    try:
        _, _, tokens = correr_motor(
            motor, carpeta, prompt_de_verificacion(informe, archivos_cambiados(carpeta, base)), nivel
        )
    except (SinCupo, RuntimeError) as error:  # lo que ya hizo se sube igual: el CI sigue siendo la puerta
        paso(f"No se pudo corregir antes de subir: {error}")
        return informe, False, 0
    (carpeta / ARCHIVO_CUERPO).unlink(missing_ok=True)
    return *verificar(carpeta, base), tokens


def atender_conflicto_sin_agente(pr, carpeta):
    """Si el script ya resolvió los conflictos, sube la fusión y cierra el pedido; False si hace falta un agente."""
    numero, rama = pr["number"], pr["headRefName"]
    if archivos_en_conflicto(carpeta):
        return False
    titulo = f"Integra main en {rama}"
    if (aviso := asegurar_cache(carpeta, archivos_cambiados(carpeta))) is not None:
        paso(aviso)
    if not integrar_main(carpeta, rama, titulo):
        return False
    cadena.comentar(
        numero, f"{MARCA_HECHO}\n{medida_del_respaldo('script', 0, 0)}\nConflictos con main resueltos por script."
    )
    git("worktree", "remove", "--force", str(carpeta), chequear=False)
    SESION["atendidos"].append({"pr": numero, "resultado": "listo", "minutos": 0, "tokens": 0, "motor": "script"})
    paso(f"Listo el PR #{numero}: conflictos resueltos sin agente.")
    return True


def atender(pr, pedido, nivel=None, motor="codex"):
    """Implementa o corrige el pedido con Codex o, si `motor` es un modelo de Claude, con el respaldo."""
    numero, rama = pr["number"], pr["headRefName"]
    nivel = nivel or esfuerzo()
    nombre = "Codex" if motor == "codex" else motor.capitalize()
    try:
        cadena.marcar_tomado(numero, pedido)
    except RuntimeError as error:  # sin la marca, `vigilar` puede avisar de más; no frena el trabajo
        paso(f"No pude marcar el pedido como tomado: {error}")
    numero_issue = cadena.numero_de_rama(rama)
    comienzo = time.monotonic()
    paso(f"Preparando el worktree de {rama} (fetch + fusión con main)…")
    carpeta = preparar_worktree(rama, numero_issue)
    punto_de_partida = git("rev-parse", "HEAD", cwd=carpeta).stdout.strip()
    if cadena.origen_de(pedido) == "conflicto" and atender_conflicto_sin_agente(pr, carpeta):
        return
    paso("Leyendo las revisiones pendientes del PR…")
    prompt = prompt_para_codex(pedido, revisiones_pendientes(numero))
    detalle = f"esfuerzo {nivel}" if motor == "codex" else "respaldo por falta de cupo de Codex"
    paso(f"Corriendo {nombre} ({detalle}, límite {LIMITE_MINUTOS} min); su salida va con │:")
    inicio = time.monotonic()
    codigo, texto, tokens = correr_motor(motor, carpeta, prompt, nivel)
    minutos_codex = (time.monotonic() - inicio) / 60
    paso(f"{nombre} terminó con código {codigo} en {minutos_codex:.1f} min ({tokens:,} tokens).")

    def medida():
        return (
            medida_de_codex(minutos_codex, tokens, nivel)
            if motor == "codex"
            else medida_del_respaldo(motor, minutos_codex, tokens)
        )

    archivo_cuerpo = carpeta / ARCHIVO_CUERPO
    cuerpo = cuerpo_del_pr(archivo_cuerpo.read_text(encoding="utf-8") if archivo_cuerpo.exists() else "", numero_issue)
    archivo_cuerpo.unlink(missing_ok=True)  # no debe viajar en el commit
    pregunta = cadena.pregunta_de_criterio(texto)
    if pregunta:
        cadena.gh("issue", "comment", str(numero_issue), "--body", f"Duda de Codex (PR #{numero}):\n\n> {pregunta}")
        cadena.etiquetar(
            numero_issue, agregar=["necesita-criterio"], quitar=["estado:en-curso", "agente:codex"], tipo="issue"
        )
        cadena.comentar(
            numero,
            f"{MARCA_HECHO}\n{medida()}\n{nombre} tiene una duda de criterio; quedó en el issue #{numero_issue}.",
        )
        paso(f"Duda de criterio: quedó en el issue #{numero_issue} (necesita-criterio).")
        avisar("Implementador", f"PR #{numero}: {nombre} tiene una duda de criterio.")
        SESION["atendidos"].append(
            {"pr": numero, "resultado": "duda", "minutos": minutos_codex, "tokens": tokens, "motor": motor}
        )
        return
    if codigo != 0:
        raise RuntimeError(f"{nombre} terminó con código {codigo}.\n\n{texto[-1500:]}")
    paso("Verificando aquí (formato, ruff y pruebas del módulo tocado)…")
    informe, bien = verificar(carpeta, punto_de_partida)
    paso("\n".join(informe))
    if not bien:
        inicio = time.monotonic()
        informe, bien, tokens_extra = corregir_lo_verificado(carpeta, motor, nivel, informe, punto_de_partida)
        tokens += tokens_extra
        minutos_codex += (time.monotonic() - inicio) / 60
        paso("\n".join(informe))
    paso("Haciendo commit y push de los cambios…")
    titulo = f"{pr['title']} (#{numero_issue})"
    if not subir_cambios(carpeta, rama, titulo):
        # Sin commit no hay CI ni revisión nueva: un «hecho» dejaría el PR parado, aunque Codex haya escrito el cuerpo.
        # Si es un pedido de implementar y la rama ya trae el trabajo, alcanza con que corran el CI y la revisión.
        es_implementar = cadena.MARCA_PEDIDO in pedido and cadena.MARCA_CORREGIR not in pedido
        if not es_implementar or not archivos_cambiados(carpeta):
            raise RuntimeError(
                f"{nombre} terminó sin cambios y sin una línea `{cadena.PEDIDO_CRITERIO}`.\n\n{texto[-1500:]}"
            )
        paso("La rama ya trae el trabajo: subo un commit vacío para que corran el CI y la revisión.")
        relanzar_ci(carpeta, rama, titulo)
    resumen = git("show", "--stat", "--format=", "HEAD", cwd=carpeta).stdout.strip()
    paso(f"Cambios subidos:\n{resumen}")
    if cuerpo:
        paso("Actualizando el cuerpo del PR…")
        cadena.gh("pr", "edit", str(numero), "--body", cuerpo)
    paso("Comentando «hecho» en el PR…")
    verificacion = "\n".join(f"- {linea}" for linea in informe)
    cadena.comentar(
        numero,
        f"{MARCA_HECHO}\n{medida()}\n"
        f"Implementado en esta PC con {nombre}.\n\n{texto[-1500:]}\n\n"
        f"Verificación del implementador (fuera del sandbox):\n{verificacion}",
    )
    git("worktree", "remove", "--force", str(carpeta), chequear=False)
    minutos = (time.monotonic() - comienzo) / 60
    resultado = "listo" if bien else "subido con observaciones"
    SESION["atendidos"].append(
        {"pr": numero, "resultado": resultado, "minutos": minutos_codex, "tokens": tokens, "motor": motor}
    )
    paso(f"Listo el PR #{numero} ({minutos:.1f} min en total).")
    avisar("Implementador", f"PR #{numero} {resultado} ({minutos:.0f} min). Queda la revisión de la cadena.")


def limpiar_carpetas():
    """Borra las carpetas de trabajo de los PR cerrados; las que el sandbox de Codex deja trabadas se avisan una vez."""
    if not CARPETA_TRABAJO.exists():
        return
    abiertos = {cadena.numero_de_rama(pr["headRefName"]) for pr in cadena.prs_de_codex()}
    nombres = [c.name for c in CARPETA_TRABAJO.iterdir() if c.is_dir()]
    for nombre in carpetas_sobrantes(nombres, abiertos):
        if nombre in SESION["sin_borrar"]:
            continue
        carpeta = CARPETA_TRABAJO / nombre
        git("worktree", "remove", "--force", str(carpeta), chequear=False)
        shutil.rmtree(carpeta, ignore_errors=True)
        if carpeta.exists():
            SESION["sin_borrar"].add(nombre)
            paso(f"No pude borrar {carpeta} (quedan archivos del sandbox de Codex): borrala a mano.")
        else:
            paso(f"Borré {carpeta}: su PR ya se cerró.")
    git("worktree", "prune", chequear=False)


def una_vuelta(solo_pr=None, simular=False):
    """Atiende el primer pedido pendiente; True si había trabajo. Con `simular` solo informa y devuelve False."""
    for pr in cadena.prs_de_codex():
        if solo_pr is not None and pr["number"] != solo_pr:
            continue
        if "bloqueado" in cadena.etiquetas_de(pr):
            if solo_pr is not None:
                paso(f"El PR #{pr['number']} está `bloqueado`: lo desbloquea el dueño.")
            continue
        if time.time() < SESION["reintentar_desde"].get(pr["number"], 0):
            continue
        comentarios = cadena.comentarios_del_pr(pr["number"])
        pedido, fallos = pedido_pendiente(comentarios)
        if simular:
            if pedido is None:
                paso(f"[simulación] PR #{pr['number']}: sin pedidos pendientes.")
            elif fallos >= MAX_FALLOS:
                paso(f"[simulación] PR #{pr['number']}: lo marcaría `bloqueado` ({fallos} fallos).")
            else:
                paso(f"[simulación] PR #{pr['number']}: atendería «{pedido.strip().splitlines()[-1][:80]}».")
            continue
        if pedido is None or fallos >= MAX_FALLOS:
            if pedido is not None:
                cadena.etiquetar(pr["number"], agregar=["bloqueado"])
                cadena.comentar(
                    pr["number"], f"El implementador falló {MAX_FALLOS} veces: queda `bloqueado` para el dueño."
                )
                avisar("Implementador", f"PR #{pr['number']} quedó bloqueado tras {MAX_FALLOS} fallos.")
            continue
        modelo_respaldo = respaldo()
        motor = motor_para_ahora(time.time(), SESION["codex_sin_cupo_hasta"], modelo_respaldo)
        paso(
            f"Atendiendo el PR #{pr['number']} ({pr['headRefName']}); fallos previos: {fallos}/{MAX_FALLOS}"
            + ("" if motor == "codex" else f"; implementa {motor.capitalize()} (Codex sin cupo)")
        )
        try:
            atender(pr, pedido, esfuerzo(fallos, correcciones_previas(pedido, comentarios)), motor)
        except SinCupo as aviso:  # no cuenta como fallo: se reintenta cuando se renueve el cupo
            SESION["sin_cupo"] += 1
            if motor == "codex" and modelo_respaldo:
                SESION["codex_sin_cupo_hasta"] = time.time() + ESPERA_CUPO_SEGUNDOS
                paso(f"Codex sin cupo ({aviso}); sigue {modelo_respaldo.capitalize()} y Codex se reintenta en 15 min.")
                avisar("Implementador", f"Codex sin cupo; implementa {modelo_respaldo.capitalize()}.")
            else:
                avisar("Implementador", f"{motor.capitalize()} sin cupo; espero a que se renueve.")
                esperar_con_cuenta(ESPERA_CUPO_SEGUNDOS, f"{motor.capitalize()} sin cupo ({aviso})")
        except Exception as error:  # un fallo no frena el ciclo: queda registrado en el PR
            paso(f"Falló el PR #{pr['number']}: {error}")
            SESION["fallos"].append(pr["number"])
            SESION["reintentar_desde"][pr["number"]] = time.time() + ESPERA_REINTENTO_SEGUNDOS
            avisar("Implementador", f"Falló el PR #{pr['number']}.")
            cadena.comentar(pr["number"], f"{MARCA_FALLO}\nEl implementador falló:\n\n```\n{error}\n```")
        return True
    return False


def mostrar_estado():
    """Una línea por PR de Codex: en qué paso está y qué espera; también si hay un implementador corriendo."""
    pid = BLOQUEO.read_text(encoding="utf-8").strip() if BLOQUEO.exists() else ""
    corriendo = pid.isdigit() and proceso_vivo(int(pid))
    paso("Implementador: " + (f"corriendo (PID {pid})." if corriendo else "NO está corriendo."))
    prs = cadena.gh_json(
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,title,headRefName,labels,statusCheckRollup",
    )
    prs = [p for p in prs if p["headRefName"].startswith(cadena.PREFIJO_RAMA)]
    if not prs:
        paso("No hay PR de Codex abiertos.")
    for pr in prs:
        comentarios = cadena.comentarios_rest(pr["number"])
        pedido, _ = pedido_pendiente([c["body"] for c in comentarios])
        sensible = cadena.es_sensible(cadena.archivos_del_pr(pr["number"]))
        parada = pedido is None and cadena.correccion_parada(pr, comentarios) is not None
        etapa = etapa_del_pr(cadena.etiquetas_de(pr), pedido is not None, pr["statusCheckRollup"], sensible, parada)
        paso(f"PR #{pr['number']} ({pr['headRefName']}) {pr['title'][:50]}\n    → {etapa}")


def resumen_final():
    """Lo atendido en esta corrida y los PR de Codex que se fusionaron desde que arrancó (si `gh` responde)."""
    fusionados = []
    try:
        desde = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(SESION["inicio"]))
        hechos = cadena.gh_json(
            "pr", "list", "--state", "merged", "--search", f"merged:>={desde}", "--json", "number,headRefName"
        )
        fusionados = [p["number"] for p in hechos if p["headRefName"].startswith(cadena.PREFIJO_RAMA)]
    except Exception:  # noqa: BLE001  el resumen es informativo: sin red se muestra lo local
        pass
    if SESION["atendidos"] or SESION["fallos"] or SESION["sin_cupo"] or fusionados:
        paso(formatear_resumen(SESION, fusionados, time.time()))


def main(argv=None):
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--estado", action="store_true", help="mostrar en qué paso está cada PR de Codex")
    analizador.add_argument("--esperar", action="store_true", help="repetir cada 60 segundos")
    analizador.add_argument("--pr", type=int, help="atender solo este PR")
    analizador.add_argument("--simular", action="store_true", help="decir qué haría, sin tocar nada")
    args = analizador.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # la consola de Windows usa cp1252
    os.environ.setdefault(
        "GITHUB_REPOSITORY", cadena.gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    )
    if args.estado:
        mostrar_estado()
        return 0
    if not args.simular:
        tomar_bloqueo()
    try:
        paso("Implementador en marcha." + (" Modo --esperar: Ctrl+C para frenar." if args.esperar else ""))
        while True:
            paso("Buscando pedidos pendientes en los PR de Codex…")
            trabajo = una_vuelta(args.pr, args.simular)
            if not args.esperar:
                if not trabajo and not args.simular:
                    paso("Nada pendiente.")
                return 0
            if not trabajo:
                limpiar_carpetas()
                paso(f"Nada pendiente; vuelvo a mirar en {ESPERA_SEGUNDOS} s.")
                time.sleep(ESPERA_SEGUNDOS)
    except KeyboardInterrupt:
        paso("Detenido con Ctrl+C.")
        return 130
    finally:
        if not args.simular:
            resumen_final()
            soltar_bloqueo()


if __name__ == "__main__":
    sys.exit(main())
