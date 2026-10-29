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

Todo lo que muestra también queda en `.implementador/registro.log`. Solo corre una instancia a la vez.
"""

import argparse
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

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_TRABAJO = RAIZ / ".implementador"
REGISTRO = CARPETA_TRABAJO / "registro.log"
BLOQUEO = CARPETA_TRABAJO / "bloqueo.pid"
SONDEO_SEGUNDOS = 30  # cada cuánto se revisa si Codex sigue dando señales
INACTIVIDAD_AVISO_MINUTOS = 10  # sin una línea nueva de Codex: se avisa
INACTIVIDAD_CORTE_MINUTOS = 20  # sin una línea nueva de Codex: se lo mata y cuenta como fallo del pedido
CUENTA_REGRESIVA_SEGUNDOS = 5 * 60
LIMITE_PRUEBAS_MINUTOS = 20
SERVICE_WORKER = "gimnasio/static/sw.js"
VERSION_SW = re.compile(r'(const VERSION = ")(\d+)(")')
SESION = {"inicio": time.time(), "atendidos": [], "fallos": [], "sin_cupo": 0}
MARCA_HECHO = "<!-- implementador:hecho -->"
MARCA_FALLO = "<!-- implementador:fallo -->"
MAX_FALLOS = 2
LIMITE_MINUTOS = 60
ESPERA_SEGUNDOS = 60
LIMITE_REVISIONES = 20000
ARCHIVO_CUERPO = ".implementador-cuerpo.md"
ESPERA_CUPO_SEGUNDOS = 15 * 60
ESFUERZO_POR_DEFECTO = "low"  # el cupo de Codex rinde más; GIMNASIO_CODEX_ESFUERZO lo cambia (low|medium|high)
PEDIDO = re.compile(r"^\s*@codex\s+(?!review\b)\S", re.IGNORECASE)


class SinCupo(RuntimeError):
    """Codex se quedó sin cupo de uso: no es un fallo del pedido, hay que esperar a que se renueve."""


# --- Lógica pura -----------------------------------------------------------


def es_falta_de_cupo(texto):
    return "hit your usage limit" in (texto or "").lower()


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
        "Escribí el cuerpo del PR (plantilla completa, con «Notas para el próximo agente», el conteo de passed/skipped "
        f"y lo que no pudiste correr) en `{ARCHIVO_CUERPO}` en la raíz: lo publica el implementador (sin `gh`).\n"
        "Para ahorrar cupo: corré ruff y solo las pruebas de los módulos que tocás (con MySQL si hace falta); la suite "
        "completa y los e2e los corre el CI, no los repitas. No lances revisiones aparte: las hace la cadena.\n"
        "Lista de control: si tocás algo de `gimnasio/static/` que no sea una prueba, subí `VERSION` en "
        "`gimnasio/static/sw.js` (si no, los navegadores con el service worker viejo no reciben el cambio); "
        "el implementador lo verifica antes de subir.\n\n"
    )
    detalle = f"\n\n--- Revisiones del PR a atender ---\n{revisiones}" if revisiones else ""
    return encabezado + texto + detalle


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


def necesita_subir_cache(archivos):
    """Tocar recursos de la PWA sin subir VERSION deja a los navegadores con el service worker viejo."""
    toca = any(
        a.startswith("gimnasio/static/") and a != SERVICE_WORKER and not a.endswith(".test.js") for a in archivos
    )
    return toca and SERVICE_WORKER not in archivos


def subir_version_sw(codigo):
    """El código del service worker con VERSION + 1; None si no encuentra la constante."""
    if not VERSION_SW.search(codigo):
        return None
    return VERSION_SW.sub(lambda m: f"{m[1]}{int(m[2]) + 1}{m[3]}", codigo, count=1)


def etapa_del_pr(etiquetas, hay_pedido, checks, sensible):
    """En qué paso de la cadena está un PR de Codex y qué espera. `checks` son los de statusCheckRollup."""
    estados = [(c.get("conclusion") or c.get("state") or "").upper() for c in checks]
    en_curso = any(c.get("status") not in (None, "COMPLETED") for c in checks) or "PENDING" in estados
    rojo = any(e in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE") for e in estados)
    if "bloqueado" in etiquetas:
        return "bloqueado: lo desbloquea el dueño"
    if hay_pedido:
        return "pedido pendiente: lo atiende el implementador"
    if en_curso:
        return "esperando el CI"
    if rojo:
        return "CI en rojo: la cadena va a pedir una corrección"
    if "correccion-pendiente" in etiquetas:
        return "corrección pendiente: la cadena la va a pedir"
    if "revisado:codex" not in etiquetas:
        return "esperando la revisión de Codex"
    if sensible and "revisado:opus" not in etiquetas:
        return "esperando la revisión de Opus (ruta sensible)"
    return "lista: la fusión automática debería ocurrir"


def formatear_resumen(sesion, fusionados, ahora):
    """El resumen de lo que hizo esta corrida del implementador, para la consola y el registro."""
    atendidos = sesion["atendidos"]
    minutos = sum(a["minutos"] for a in atendidos)
    tokens = sum(a["tokens"] for a in atendidos)
    lineas = [f"Resumen de la corrida ({(ahora - sesion['inicio']) / 60:.0f} min en marcha):"]
    for a in atendidos:
        lineas.append(f"  · PR #{a['pr']}: {a['resultado']} en {a['minutos']:.1f} min, {a['tokens']:,} tokens")
    lineas.append(
        f"  Atendidos: {len(atendidos)} · Fallos: {len(sesion['fallos'])} · Veces sin cupo: {sesion['sin_cupo']}"
    )
    lineas.append(f"  Codex: {minutos:.1f} min y {tokens:,} tokens en total")
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
    # Si hay conflictos con main, quedan en el árbol para que Codex los resuelva.
    git("merge", "origin/main", "--no-edit", cwd=carpeta, chequear=False)
    return carpeta


def esfuerzo():
    return os.environ.get("GIMNASIO_CODEX_ESFUERZO") or ESFUERZO_POR_DEFECTO


def comando_codex(binario, carpeta, salida):
    return [
        binario,
        "exec",
        "-C",
        str(carpeta),
        "-s",
        "workspace-write",
        "-c",
        f'model_reasoning_effort="{esfuerzo()}"',
    ] + [
        "-o",
        str(salida),
        "-",
    ]


def correr_codex(carpeta, prompt):
    binario = binario_codex()
    if binario is None:
        raise RuntimeError("No encuentro Codex: definí GIMNASIO_CODEX_BIN con la ruta de codex.exe.")
    salida = carpeta / ".implementador-ultimo.txt"
    proceso = subprocess.Popen(
        comando_codex(binario, carpeta, salida),
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


def _seguir_a_codex(proceso, lineas):
    """Muestra lo que dice Codex y lo corta si pasa el límite total o si se queda mudo; devuelve sus líneas."""
    inicio = ultima_senal = time.monotonic()
    avisado = False
    registro = []
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
            mostrar(f"   │ {linea.rstrip()}")
            ultima_senal, avisado = ahora, False
        mudo = (ahora - ultima_senal) / 60
        if ahora - inicio > LIMITE_MINUTOS * 60:
            proceso.kill()
            raise RuntimeError(f"Codex pasó el límite de {LIMITE_MINUTOS} min y se lo cortó.")
        if mudo > INACTIVIDAD_CORTE_MINUTOS:
            proceso.kill()
            raise RuntimeError(f"Codex estuvo {INACTIVIDAD_CORTE_MINUTOS} min sin dar señales y se lo cortó.")
        if mudo > INACTIVIDAD_AVISO_MINUTOS and not avisado:
            avisado = True
            paso(f"Codex lleva {mudo:.0f} min sin escribir nada; se lo corta a los {INACTIVIDAD_CORTE_MINUTOS}.")
            avisar("Implementador", "Codex lleva rato sin dar señales.")


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


# --- Verificación propia ---------------------------------------------------


def python_del_proyecto():
    """El Python del `.venv` del checkout principal (los worktrees no tienen uno propio)."""
    candidato = RAIZ / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    candidato = candidato.with_suffix(".exe") if sys.platform == "win32" else candidato
    return str(candidato) if candidato.exists() else sys.executable


def correr(comando, carpeta, minutos):
    """Corre un comando fuera del sandbox de Codex; devuelve (código, salida). Un tiempo agotado cuenta como fallo."""
    try:
        r = subprocess.run(
            comando, cwd=carpeta, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=minutos * 60,
        )  # fmt: skip
    except subprocess.TimeoutExpired:
        return 1, f"Pasaron {minutos} min sin terminar y se lo cortó."
    return r.returncode, (r.stdout + r.stderr).strip()


def archivos_cambiados(carpeta):
    """Lo que la rama cambia respecto de main, incluidos los archivos nuevos que Codex todavía no agregó."""
    cambiados = git("diff", "--name-only", "origin/main", cwd=carpeta).stdout.split()
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


def verificar(carpeta):
    """Formato, ruff y las pruebas del módulo tocado, corridos aquí: el sandbox de Codex a veces no puede.

    Devuelve (líneas del informe, True si todo salió bien). No frena la subida: el CI sigue siendo la puerta.
    """
    informe, bien = [], True
    archivos = archivos_cambiados(carpeta)
    if (aviso := asegurar_cache(carpeta, archivos)) is not None:
        informe.append(aviso)
        archivos = archivos_cambiados(carpeta)
    python = python_del_proyecto()
    fuentes = [a for a in archivos if a.endswith(".py") and (carpeta / a).exists()]
    if fuentes:
        correr([python, "-m", "ruff", "format", *fuentes], carpeta, 5)
    codigo, salida = correr([python, "-m", "ruff", "check", "."], carpeta, 5)
    informe.append("ruff: " + ("sin observaciones" if codigo == 0 else f"con hallazgos\n{salida[-800:]}"))
    bien = bien and codigo == 0
    existentes = {p.relative_to(carpeta).as_posix() for p in (carpeta / "pruebas").glob("test_*.py")}
    pruebas = tests_a_correr(archivos, existentes)
    if not pruebas:
        informe.append("pytest: sin pruebas asociadas a lo cambiado; las corre el CI.")
        return informe, bien
    codigo, salida = correr(
        [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *pruebas], carpeta, LIMITE_PRUEBAS_MINUTOS
    )
    cuenta = contar_pruebas(salida)
    detalle = ", ".join(f"{n} {palabra}" for palabra, n in cuenta.items()) or "sin resumen"
    informe.append(f"pytest ({len(pruebas)} archivos): {detalle}" + ("" if codigo == 0 else f"\n{salida[-800:]}"))
    if cuenta.get("skipped") and not os.environ.get("GIMNASIO_BD_HOST"):
        informe.append("⚠ Hay pruebas saltadas y no está `GIMNASIO_BD_HOST`: un «skipped» no cuenta como verde.")
    return informe, bien and codigo == 0


# --- Pasos -----------------------------------------------------------------


def revisiones_pendientes(numero):
    """Revisiones y comentarios en línea del PR posteriores al último «hecho» del implementador."""
    comentarios = cadena.gh_json("pr", "view", str(numero), "--json", "comments")["comments"]
    desde = max((c["createdAt"] for c in comentarios if MARCA_HECHO in c["body"]), default="")
    repo = cadena.repo()
    resenas = cadena.gh_json("api", f"repos/{repo}/pulls/{numero}/reviews")
    en_linea = cadena.gh_json("api", f"repos/{repo}/pulls/{numero}/comments")
    return texto_de_revisiones(resenas, en_linea, desde)


def atender(pr, pedido):
    numero, rama = pr["number"], pr["headRefName"]
    numero_issue = cadena.numero_de_rama(rama)
    comienzo = time.monotonic()
    paso(f"Preparando el worktree de {rama} (fetch + fusión con main)…")
    carpeta = preparar_worktree(rama, numero_issue)
    paso("Leyendo las revisiones pendientes del PR…")
    prompt = prompt_para_codex(pedido, revisiones_pendientes(numero))
    paso(f"Corriendo Codex (esfuerzo {esfuerzo()}, límite {LIMITE_MINUTOS} min); su salida va con │:")
    inicio = time.monotonic()
    codigo, texto, tokens = correr_codex(carpeta, prompt)
    minutos_codex = (time.monotonic() - inicio) / 60
    paso(f"Codex terminó con código {codigo} en {minutos_codex:.1f} min ({tokens:,} tokens).")
    archivo_cuerpo = carpeta / ARCHIVO_CUERPO
    cuerpo = cuerpo_del_pr(archivo_cuerpo.read_text(encoding="utf-8") if archivo_cuerpo.exists() else "", numero_issue)
    archivo_cuerpo.unlink(missing_ok=True)  # no debe viajar en el commit
    pregunta = cadena.pregunta_de_criterio(texto)
    if pregunta:
        cadena.gh("issue", "comment", str(numero_issue), "--body", f"Duda de Codex (PR #{numero}):\n\n> {pregunta}")
        cadena.etiquetar(
            numero_issue, agregar=["necesita-criterio"], quitar=["estado:en-curso", "agente:codex"], tipo="issue"
        )
        cadena.comentar(numero, f"{MARCA_HECHO}\nCodex tiene una duda de criterio; quedó en el issue #{numero_issue}.")
        paso(f"Duda de criterio: quedó en el issue #{numero_issue} (necesita-criterio).")
        avisar("Implementador", f"PR #{numero}: Codex tiene una duda de criterio.")
        SESION["atendidos"].append({"pr": numero, "resultado": "duda", "minutos": minutos_codex, "tokens": tokens})
        return
    if codigo != 0:
        raise RuntimeError(f"Codex terminó con código {codigo}.\n\n{texto[-1500:]}")
    paso("Verificando aquí (formato, ruff y pruebas del módulo tocado)…")
    informe, bien = verificar(carpeta)
    paso("\n".join(informe))
    paso("Haciendo commit y push de los cambios…")
    if not subir_cambios(carpeta, rama, f"{pr['title']} (#{numero_issue})"):
        raise RuntimeError(f"Codex terminó con código {codigo} y no dejó cambios que subir.\n\n{texto[-1500:]}")
    resumen = git("show", "--stat", "--format=", "HEAD", cwd=carpeta).stdout.strip()
    paso(f"Cambios subidos:\n{resumen}")
    if cuerpo:
        paso("Actualizando el cuerpo del PR…")
        cadena.gh("pr", "edit", str(numero), "--body", cuerpo)
    paso("Comentando «hecho» en el PR…")
    verificacion = "\n".join(f"- {linea}" for linea in informe)
    cadena.comentar(
        numero,
        f"{MARCA_HECHO}\nImplementado en esta PC con Codex.\n\n{texto[-1500:]}\n\n"
        f"Verificación del implementador (fuera del sandbox):\n{verificacion}",
    )
    git("worktree", "remove", "--force", str(carpeta), chequear=False)
    minutos = (time.monotonic() - comienzo) / 60
    resultado = "listo" if bien else "subido con observaciones"
    SESION["atendidos"].append({"pr": numero, "resultado": resultado, "minutos": minutos_codex, "tokens": tokens})
    paso(f"Listo el PR #{numero} ({minutos:.1f} min en total).")
    avisar("Implementador", f"PR #{numero} {resultado} ({minutos:.0f} min). Queda la revisión de la cadena.")


def una_vuelta(solo_pr=None, simular=False):
    """Atiende el primer pedido pendiente; True si había trabajo. Con `simular` solo informa y devuelve False."""
    for pr in cadena.prs_de_codex():
        if solo_pr is not None and pr["number"] != solo_pr:
            continue
        if "bloqueado" in cadena.etiquetas_de(pr):
            if solo_pr is not None:
                paso(f"El PR #{pr['number']} está `bloqueado`: lo desbloquea el dueño.")
            continue
        pedido, fallos = pedido_pendiente(cadena.comentarios_del_pr(pr["number"]))
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
        paso(f"Atendiendo el PR #{pr['number']} ({pr['headRefName']}); fallos previos: {fallos}/{MAX_FALLOS}")
        try:
            atender(pr, pedido)
        except SinCupo as aviso:  # no cuenta como fallo: se reintenta cuando se renueve el cupo
            avisar("Implementador", "Codex sin cupo; espero a que se renueve.")
            SESION["sin_cupo"] += 1
            esperar_con_cuenta(ESPERA_CUPO_SEGUNDOS, f"Codex sin cupo ({aviso})")
        except Exception as error:  # un fallo no frena el ciclo: queda registrado en el PR
            paso(f"Falló el PR #{pr['number']}: {error}")
            SESION["fallos"].append(pr["number"])
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
        pedido, _ = pedido_pendiente(cadena.comentarios_del_pr(pr["number"]))
        sensible = cadena.es_sensible(cadena.archivos_del_pr(pr["number"]))
        etapa = etapa_del_pr(cadena.etiquetas_de(pr), pedido is not None, pr["statusCheckRollup"], sensible)
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
