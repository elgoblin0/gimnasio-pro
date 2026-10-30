"""Pruebas de la lógica pura del implementador local (sin gh, git ni Codex)."""

import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import implementador  # noqa: E402  (necesita scripts/ en sys.path, que se agrega arriba)

HECHO = implementador.MARCA_HECHO
FALLO = implementador.MARCA_FALLO


def test_distingue_los_pedidos_de_trabajo_de_la_revision():
    assert implementador.es_pedido("@codex implementá el issue #5")
    assert implementador.es_pedido("<!-- cadena:corregir -->\n@codex el CI falló")
    assert not implementador.es_pedido("<!-- cadena:revisar abc -->\n@codex review")
    assert not implementador.es_pedido("Resumen del CI: ✅")
    assert not implementador.es_pedido(None)


def test_resumen_de_codex_deja_una_linea_por_accion():
    salida = (
        "OpenAI Codex v0.165\n--------\nmodel: gpt-6.1-sol\nreasoning effort: low\n--------\n"
        "user\nTrabajás en un worktree\nmás prompt\n"
        "codex\nVoy a revisar el cambio.\nsegundo párrafo\n"
        "exec\n\"C:\\\\WINDOWS\\\\powershell.exe\" -Command 'Get-Content AGENTS.md' in C:\\Users\\x\\issue-1\n"
        " succeeded in 284ms:\n# AGENTS.md\ncontenido largo\n"
        "exec\n\"C:\\\\WINDOWS\\\\powershell.exe\" -Command 'pytest -q' in C:\\Users\\x\\issue-1\n"
        " exited 1 in 213ms:\nprimer error\nsegundo error\ntercero\n"
        "apply patch\npatch: completed\nC:\\Users\\x\\.implementador\\issue-143\\gimnasio\\static\\sw.js\n"
        'diff --git a/gimnasio/static/sw.js b/gimnasio/static/sw.js\n+const VERSION = "17"\n'
        "tokens used\n22,704\nCorregido.\n"
    )
    resumen = implementador.ResumenDeCodex()
    visibles = [v for linea in salida.splitlines() for v in resumen.procesar(linea)]
    assert visibles == [
        "model: gpt-6.1-sol",
        "reasoning effort: low",
        "💬 Voy a revisar el cambio.",
        "$ 'Get-Content AGENTS.md'",
        "  ✓ 284ms",
        "$ 'pytest -q'",
        "  ✗ código 1 (213ms)",
        "    primer error",
        "    segundo error",
        "✎ edita gimnasio\\static\\sw.js",
        "tokens: 22,704",
    ]


def test_toma_el_ultimo_pedido_sin_atender():
    comentarios = ["@codex implementá #5", "respuesta del bot", f"{HECHO}\nlisto", "@codex corregí"]
    assert implementador.pedido_pendiente(comentarios) == ("@codex corregí", 0)


def test_un_pedido_atendido_no_queda_pendiente():
    assert implementador.pedido_pendiente(["@codex implementá #5", f"{HECHO}\nlisto"]) == (None, 0)


def test_cuenta_los_fallos_del_pedido_vigente():
    comentarios = ["@codex implementá #5", f"{FALLO}\nuno", f"{FALLO}\ndos"]
    assert implementador.pedido_pendiente(comentarios) == ("@codex implementá #5", 2)
    assert implementador.pedido_pendiente([*comentarios, "@codex corregí"]) == ("@codex corregí", 0)


def test_el_prompt_quita_la_mencion_y_las_marcas():
    prompt = implementador.prompt_para_codex("<!-- cadena:corregir -->\n@codex el CI falló: arreglalo")
    assert prompt.endswith("el CI falló: arreglalo")
    assert "@codex" not in prompt and "<!--" not in prompt


def test_las_revisiones_posteriores_al_ultimo_hecho_entran_al_prompt():
    resenas = [
        {"user": {"login": "claude"}, "body": "Quitá la deduplicación.", "submitted_at": "2026-10-29T12:50:00Z"},
        {"user": {"login": "claude"}, "body": "Vieja.", "submitted_at": "2026-10-29T10:00:00Z"},
        {
            "user": {"login": "bot"},
            "body": "<!-- codex-review-receipt:v1 --> ruido",
            "submitted_at": "2026-10-29T12:51:00Z",
        },
    ]
    en_linea = [
        {
            "user": {"login": "bot"},
            "path": "a.py",
            "line": 7,
            "body": "P1 falta consentimiento",
            "created_at": "2026-10-29T12:49:00Z",
        }
    ]
    texto = implementador.texto_de_revisiones(resenas, en_linea, "2026-10-29T11:00:00Z")
    assert "Quitá la deduplicación." in texto
    assert "a.py:7" in texto and "P1 falta consentimiento" in texto
    assert "Vieja." not in texto and "ruido" not in texto
    prompt = implementador.prompt_para_codex("@codex atendé la revisión", texto)
    assert "Quitá la deduplicación." in prompt
    assert implementador.prompt_para_codex("@codex hacé algo").endswith("hacé algo")


def test_el_cuerpo_del_pr_empieza_con_closes():
    assert implementador.cuerpo_del_pr("Closes #89\n\nNotas", 89) == "Closes #89\n\nNotas"
    assert implementador.cuerpo_del_pr("Notas", 90) == "Closes #90\n\nNotas"
    assert implementador.cuerpo_del_pr("  \n", 90) is None
    assert implementador.cuerpo_del_pr(None, 90) is None
    assert implementador.ARCHIVO_CUERPO in implementador.prompt_para_codex("@codex hacé algo")


def test_reconoce_la_falta_de_cupo_de_codex():
    assert implementador.es_falta_de_cupo("ERROR: You've hit your usage limit. Upgrade to Pro")
    assert not implementador.es_falta_de_cupo("Codex terminó con código 1")
    assert not implementador.es_falta_de_cupo(None)


def test_el_esfuerzo_de_codex_es_bajo_salvo_que_se_pida_otro(monkeypatch):
    monkeypatch.delenv("GIMNASIO_CODEX_ESFUERZO", raising=False)
    assert implementador.esfuerzo() == "low"
    monkeypatch.setenv("GIMNASIO_CODEX_ESFUERZO", "high")
    assert implementador.esfuerzo() == "high"


# --- Ejecución de Codex, bloqueo y aviso (con un Codex falso) ------------------------------------------------


import pytest  # noqa: E402


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Registro y bloqueo en una carpeta temporal, sin avisos de Windows ni esperas reales."""
    monkeypatch.setattr(implementador, "CARPETA_TRABAJO", tmp_path / "trabajo")
    monkeypatch.setattr(implementador, "REGISTRO", tmp_path / "trabajo" / "registro.log")
    monkeypatch.setattr(implementador, "CRUDO", tmp_path / "trabajo" / "codex-crudo.log")
    monkeypatch.setattr(implementador, "BLOQUEO", tmp_path / "trabajo" / "bloqueo.pid")
    monkeypatch.setattr(implementador, "SONDEO_SEGUNDOS", 0.05)
    avisos = []
    monkeypatch.setattr(implementador, "avisar", lambda titulo, mensaje: avisos.append(mensaje))
    monkeypatch.setattr(implementador, "binario_codex", lambda: sys.executable)
    return avisos


def _codex_falso(monkeypatch, tmp_path, guion):
    archivo = tmp_path / "codex_falso.py"
    archivo.write_text(guion, encoding="utf-8", newline="\n")
    monkeypatch.setattr(
        implementador,
        "comando_codex",
        lambda binario, carpeta, salida, nivel=None: [binario, str(archivo), str(salida)],
    )
    carpeta = tmp_path / "arbol"
    carpeta.mkdir()
    return carpeta


def test_muestra_la_salida_de_codex_resumida_y_la_guarda_cruda(entorno, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GIMNASIO_IMPL_VERBOSO", raising=False)
    carpeta = _codex_falso(
        monkeypatch,
        tmp_path,
        "import sys\nprint('pensando')\nprint(sys.stdin.read().strip())\nprint('tokens used\\n1,234')\n"
        "open(sys.argv[1], 'w').write('respuesta final')\n",
    )
    codigo, texto, tokens = implementador.correr_codex(carpeta, "el pedido")
    assert (codigo, texto, tokens) == (0, "respuesta final", 1234)
    salida = capsys.readouterr().out
    assert "│ tokens: 1,234" in salida and "pensando" not in salida
    assert "pensando" in implementador.CRUDO.read_text(encoding="utf-8")


def test_con_verboso_muestra_la_salida_entera(entorno, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GIMNASIO_IMPL_VERBOSO", "1")
    carpeta = _codex_falso(
        monkeypatch,
        tmp_path,
        "import sys\nprint('pensando')\nprint(sys.stdin.read().strip())\n"
        "open(sys.argv[1], 'w').write('respuesta final')\n",
    )
    implementador.correr_codex(carpeta, "el pedido")
    salida = capsys.readouterr().out
    assert "│ pensando" in salida and "│ el pedido" in salida
    assert "pensando" in implementador.REGISTRO.read_text(encoding="utf-8")


def test_detecta_la_falta_de_cupo(entorno, tmp_path, monkeypatch):
    carpeta = _codex_falso(
        monkeypatch, tmp_path, "import sys\nprint('You hit your usage limit. Volvé mañana')\nsys.exit(1)\n"
    )
    with pytest.raises(implementador.SinCupo, match="usage limit"):
        implementador.correr_codex(carpeta, "x")


def test_corta_a_codex_si_se_queda_mudo_y_avisa(entorno, tmp_path, monkeypatch):
    monkeypatch.setattr(implementador, "INACTIVIDAD_AVISO_MINUTOS", 0.001)
    monkeypatch.setattr(implementador, "INACTIVIDAD_CORTE_MINUTOS", 0.003)
    carpeta = _codex_falso(monkeypatch, tmp_path, "import time\ntime.sleep(60)\n")
    with pytest.raises(RuntimeError, match="sin dar señales"):
        implementador.correr_codex(carpeta, "x")
    assert any("sin dar señales" in aviso for aviso in entorno)


def test_corta_a_codex_al_pasar_el_limite_total(entorno, tmp_path, monkeypatch):
    monkeypatch.setattr(implementador, "LIMITE_MINUTOS", 0.002)
    carpeta = _codex_falso(
        monkeypatch, tmp_path, "import time\nwhile True:\n    print('sigo', flush=True)\n    time.sleep(0.05)\n"
    )
    with pytest.raises(RuntimeError, match="límite"):
        implementador.correr_codex(carpeta, "x")


def test_no_deja_correr_dos_implementadores(entorno):
    implementador.tomar_bloqueo()
    assert implementador.BLOQUEO.read_text(encoding="utf-8") == str(implementador.os.getpid())
    implementador.soltar_bloqueo()
    assert not implementador.BLOQUEO.exists()


def test_rechaza_el_bloqueo_de_un_proceso_vivo(entorno, monkeypatch):
    implementador.CARPETA_TRABAJO.mkdir()
    implementador.BLOQUEO.write_text("4242", encoding="utf-8")
    monkeypatch.setattr(implementador, "proceso_vivo", lambda pid: True)
    with pytest.raises(SystemExit, match="4242"):
        implementador.tomar_bloqueo()


def test_ignora_un_bloqueo_viejo(entorno, monkeypatch):
    implementador.CARPETA_TRABAJO.mkdir()
    implementador.BLOQUEO.write_text("4242", encoding="utf-8")
    monkeypatch.setattr(implementador, "proceso_vivo", lambda pid: False)
    implementador.tomar_bloqueo()
    assert implementador.BLOQUEO.read_text(encoding="utf-8") == str(implementador.os.getpid())


def test_reconoce_procesos_vivos_y_muertos():
    assert implementador.proceso_vivo(implementador.os.getpid())
    proceso = implementador.subprocess.Popen([sys.executable, "-c", "pass"])
    proceso.wait()
    assert not implementador.proceso_vivo(proceso.pid)


def test_simular_no_toca_nada(entorno, monkeypatch, capsys):
    pr = {"number": 7, "headRefName": "codex/issue-3", "labels": [], "title": "t"}
    monkeypatch.setattr(implementador.cadena, "prs_de_codex", lambda: [pr, {**pr, "number": 8}])
    monkeypatch.setattr(
        implementador.cadena, "comentarios_del_pr", lambda n: ["@codex implementá #3"] if n == 7 else []
    )
    monkeypatch.setattr(implementador, "atender", lambda *a: pytest.fail("no debe atender"))
    assert implementador.una_vuelta(simular=True) is False
    salida = capsys.readouterr().out
    assert "PR #7: atendería" in salida and "PR #8: sin pedidos" in salida


def test_pr_filtra_el_pedido_a_atender(entorno, monkeypatch):
    atendidos = []
    prs = [{"number": n, "headRefName": f"codex/issue-{n}", "labels": [], "title": "t"} for n in (7, 8)]
    monkeypatch.setattr(implementador.cadena, "prs_de_codex", lambda: prs)
    monkeypatch.setattr(implementador.cadena, "comentarios_del_pr", lambda n: ["@codex implementá"])
    monkeypatch.setattr(implementador, "atender", lambda pr, pedido, nivel=None: atendidos.append(pr["number"]))
    assert implementador.una_vuelta(solo_pr=8) is True
    assert atendidos == [8]


# --- Qué cuenta como atendido ---------------------------------------------------------------------------------


PEDIDO_CORREGIR = f"{implementador.cadena.MARCA_CORREGIR}\natendé la revisión de Opus"
PR_DE_CODEX = {"number": 7, "headRefName": "codex/issue-3", "labels": [], "title": "t"}


@pytest.fixture
def atencion(entorno, tmp_path, monkeypatch):
    """`atender` sin git, gh ni Codex: `responder` fija lo que hace Codex y `publicado` junta lo que llegó al PR."""
    carpeta = tmp_path / "arbol"
    carpeta.mkdir()
    publicado = SimpleNamespace(comentarios=[], gh=[], etiquetas=[])

    def responder(texto, cuerpo=None, cambios=False):
        def correr_codex(carpeta_codex, prompt, nivel=None):
            if cuerpo:
                (carpeta_codex / implementador.ARCHIVO_CUERPO).write_text(cuerpo, encoding="utf-8", newline="\n")
            return 0, texto, 10

        monkeypatch.setattr(implementador, "correr_codex", correr_codex)
        monkeypatch.setattr(implementador, "subir_cambios", lambda *a: cambios)

    monkeypatch.setattr(implementador.cadena, "marcar_tomado", lambda *a: None)
    monkeypatch.setattr(implementador.cadena, "gh", lambda *a: publicado.gh.append(a))
    monkeypatch.setattr(implementador.cadena, "comentar", lambda numero, texto: publicado.comentarios.append(texto))
    monkeypatch.setattr(implementador.cadena, "etiquetar", lambda *a, **k: publicado.etiquetas.append(k))
    monkeypatch.setattr(implementador, "preparar_worktree", lambda rama, numero: carpeta)
    monkeypatch.setattr(implementador, "revisiones_pendientes", lambda numero: "")
    monkeypatch.setattr(implementador, "verificar", lambda c: (["ruff: sin observaciones"], True))
    monkeypatch.setattr(implementador, "git", lambda *a, **k: SimpleNamespace(stdout=""))
    return SimpleNamespace(responder=responder, publicado=publicado)


@pytest.mark.parametrize("pedido", [PEDIDO_CORREGIR, f"{implementador.cadena.MARCA_PEDIDO}\nimplementá el issue #3"])
def test_terminar_sin_cambios_aunque_deje_cuerpo_no_cuenta_como_atendido(atencion, pedido):
    atencion.responder("Necesito criterio, no modifiqué código.", cuerpo="Pedido detenido.")
    with pytest.raises(RuntimeError, match="sin cambios"):
        implementador.atender(PR_DE_CODEX, pedido)
    assert not any(implementador.MARCA_HECHO in c for c in atencion.publicado.comentarios)
    assert atencion.publicado.gh == []  # el texto de Codex no reemplaza el cuerpo del PR


def test_terminar_sin_cambios_ni_cuerpo_tampoco_cuenta(atencion):
    atencion.responder("No hice nada.")
    with pytest.raises(RuntimeError, match="sin cambios"):
        implementador.atender(PR_DE_CODEX, PEDIDO_CORREGIR)


def test_un_pedido_sin_cambios_termina_bloqueado_al_llegar_al_tope(atencion, monkeypatch):
    atencion.responder("Necesito criterio.", cuerpo="Pedido detenido.")
    comentarios = [PEDIDO_CORREGIR]
    monkeypatch.setattr(implementador.cadena, "prs_de_codex", lambda: [PR_DE_CODEX])
    monkeypatch.setattr(implementador.cadena, "comentarios_del_pr", lambda n: comentarios)
    monkeypatch.setattr(implementador.cadena, "comentar", lambda n, texto: comentarios.append(texto))
    for _ in range(implementador.MAX_FALLOS):
        assert implementador.una_vuelta() is True
    assert all(implementador.MARCA_FALLO in c for c in comentarios[1:])
    assert implementador.una_vuelta() is False
    assert atencion.publicado.etiquetas == [{"agregar": ["bloqueado"]}]


def test_con_cambios_publica_el_cuerpo_y_cierra_el_pedido(atencion):
    atencion.responder("Corregido.", cuerpo="Closes #3\n\nCuerpo.", cambios=True)
    implementador.atender(PR_DE_CODEX, PEDIDO_CORREGIR)
    assert implementador.MARCA_HECHO in atencion.publicado.comentarios[-1]
    assert atencion.publicado.gh == [("pr", "edit", "7", "--body", "Closes #3\n\nCuerpo.")]


def test_una_duda_reconocida_cierra_el_pedido_sin_cambios(atencion):
    atencion.responder("Lo pensé.\nNECESITA-CRITERIO: ¿dónde guardo el hecho?", cuerpo="Pedido detenido.")
    implementador.atender(PR_DE_CODEX, PEDIDO_CORREGIR)
    assert implementador.MARCA_HECHO in atencion.publicado.comentarios[-1]
    assert atencion.publicado.etiquetas[0]["agregar"] == ["necesita-criterio"]
    assert not any(a[:2] == ("pr", "edit") for a in atencion.publicado.gh)


def test_el_prompt_exige_el_prefijo_exacto_de_la_duda():
    prompt = implementador.prompt_para_codex(PEDIDO_CORREGIR)
    assert f"empieza exactamente con `{implementador.cadena.PEDIDO_CRITERIO}`" in prompt
    assert "cuenta como fallo" in prompt


def test_etapa_de_una_correccion_parada():
    etapa = implementador.etapa_del_pr
    verde = [{"status": "COMPLETED", "conclusion": "SUCCESS"}]
    rojo = [{"status": "COMPLETED", "conclusion": "FAILURE"}]
    etiquetas = {"correccion-pendiente"}
    assert "la cadena la va a pedir" in etapa(etiquetas, False, verde, False)
    for checks in (verde, rojo):
        assert "nadie la va a volver a pedir" in etapa(etiquetas, False, checks, False, parada=True)
    assert "lo atiende el implementador" in etapa(etiquetas, True, verde, False, parada=True)
    assert "lo desbloquea el dueño" in etapa(etiquetas | {"bloqueado"}, False, verde, False, parada=True)


def test_el_estado_distingue_la_correccion_parada(entorno, monkeypatch, capsys):
    pr = {**PR_DE_CODEX, "labels": [{"name": "correccion-pendiente"}], "statusCheckRollup": []}
    comentarios = [
        {"body": PEDIDO_CORREGIR, "created_at": "2026-10-29T10:00:00Z"},
        {"body": implementador.MARCA_HECHO, "created_at": "2026-10-29T10:05:00Z"},
    ]
    respuestas = {"commits": {"commits": [{"committedDate": "2026-10-29T09:00:00Z"}]}, "labels": {"labels": []}}
    monkeypatch.setattr(
        implementador.cadena, "gh_json", lambda *a: [pr] if a[:2] == ("pr", "list") else respuestas[a[-1]]
    )
    monkeypatch.setattr(implementador.cadena, "comentarios_rest", lambda numero: comentarios)
    monkeypatch.setattr(implementador.cadena, "archivos_del_pr", lambda numero: ["scripts/cadena.py"])
    implementador.mostrar_estado()
    assert "nadie la va a volver a pedir" in capsys.readouterr().out


# --- Verificación propia, estado y resumen (lógica pura) -----------------------------------------------------


def test_lee_los_tokens_que_informa_codex():
    assert implementador.tokens_de("trabajo\ntokens used\n22,704\nlisto") == 22704
    assert implementador.tokens_de("tokens used\n1.200\n...tokens used\n3.400") == 3400
    assert implementador.tokens_de("sin cifra") == 0


def test_elige_las_pruebas_de_lo_cambiado():
    existentes = {"pruebas/test_visitas_api.py", "pruebas/test_visitas_repo.py", "pruebas/test_reglas_cupo.py"}
    assert implementador.tests_a_correr(["gimnasio/visitas/servicio.py"], existentes) == [
        "pruebas/test_visitas_api.py",
        "pruebas/test_visitas_repo.py",
    ]
    assert implementador.tests_a_correr(["pruebas/test_reglas_cupo.py", "README.md"], existentes) == [
        "pruebas/test_reglas_cupo.py"
    ]
    assert implementador.tests_a_correr(["gimnasio/static/js/a.js", "docs/x.md"], existentes) == []


def test_cuenta_el_resumen_de_pytest():
    assert implementador.contar_pruebas("....\n1 failed, 67 passed, 2 skipped in 45.45s") == {
        "failed": 1,
        "passed": 67,
        "skipped": 2,
    }
    assert implementador.contar_pruebas("ERROR collecting\n1 error in 0.30s") == {"error": 1}
    assert implementador.contar_pruebas("nada") == {}


def test_pide_subir_la_cache_solo_si_toca_recursos_sin_el_service_worker():
    sw = implementador.SERVICE_WORKER
    assert implementador.necesita_subir_cache(["gimnasio/static/js/recepcion.js"])
    assert not implementador.necesita_subir_cache(["gimnasio/static/js/recepcion.js", sw])
    assert not implementador.necesita_subir_cache(["gimnasio/static/js/modulo.test.js"])
    assert not implementador.necesita_subir_cache(["gimnasio/visitas/servicio.py"])


def test_sube_la_version_del_service_worker():
    codigo = 'const VERSION = "16";\nconst CACHE = P + VERSION;\n'
    assert implementador.subir_version_sw(codigo) == 'const VERSION = "17";\nconst CACHE = P + VERSION;\n'
    assert implementador.subir_version_sw("sin constante") is None


def test_etapa_de_cada_pr():
    verde = [{"status": "COMPLETED", "conclusion": "SUCCESS"}]
    etapa = implementador.etapa_del_pr
    assert "bloqueado" in etapa({"bloqueado"}, False, verde, False)
    assert "pedido pendiente" in etapa(set(), True, verde, False)
    assert "esperando el CI" in etapa(set(), False, [{"status": "IN_PROGRESS"}], False)
    assert "CI en rojo" in etapa(set(), False, [{"status": "COMPLETED", "conclusion": "FAILURE"}], False)
    assert "corrección pendiente" in etapa({"correccion-pendiente"}, False, verde, False)
    assert "revisión de Codex" in etapa(set(), False, verde, False)
    assert "Opus" in etapa({"revisado:codex"}, False, verde, True)
    assert "lista" in etapa({"revisado:codex", "revisado:opus"}, False, verde, True)
    assert "lista" in etapa({"revisado:codex"}, False, verde, False)


def test_resumen_de_la_corrida():
    sesion = {
        "inicio": 0,
        "atendidos": [
            {"pr": 150, "resultado": "listo", "minutos": 1.3, "tokens": 22704},
            {"pr": 155, "resultado": "duda", "minutos": 3.8, "tokens": 50000},
        ],
        "fallos": [160],
        "sin_cupo": 1,
    }
    texto = implementador.formatear_resumen(sesion, [150], 600)
    assert "10 min en marcha" in texto and "PR #155: duda" in texto
    assert "Atendidos: 2 · Fallos: 1 · Veces sin cupo: 1" in texto
    assert "72,704 tokens" in texto and "#150" in texto


def test_reconoce_los_pedidos_de_la_cadena_sin_mencion():
    issue = {"number": 7, "title": "Alta", "body": "X"}
    assert implementador.es_pedido(implementador.cadena.prompt_implementar(issue))
    assert implementador.es_pedido(implementador.cadena.prompt_corregir("el CI falló.", "ci"))
    assert not implementador.es_pedido("Pedido para el implementador local: sin marca de la cadena")


def test_el_prompt_para_codex_no_lleva_el_encabezado_local():
    pedido = implementador.cadena.prompt_corregir("el CI falló: arreglalo.", "ci")
    prompt = implementador.prompt_para_codex(pedido)
    assert "el CI falló: arreglalo." in prompt
    assert implementador.cadena.ENCABEZADO_LOCAL not in prompt and "<!--" not in prompt


def test_el_esfuerzo_sube_con_cada_fallo_o_correccion_repetida(monkeypatch):
    """Bajo en lo fácil; si un pedido ya falló o la misma corrección se repite, Codex piensa más."""
    monkeypatch.delenv("GIMNASIO_CODEX_ESFUERZO", raising=False)
    assert implementador.esfuerzo(fallos=1) == "medium"
    assert implementador.esfuerzo(previas=1) == "medium"
    assert implementador.esfuerzo(fallos=1, previas=1) == "high"
    assert implementador.esfuerzo(previas=5) == "high"
    monkeypatch.setenv("GIMNASIO_CODEX_ESFUERZO", "medium")
    assert implementador.esfuerzo(previas=1) == "high"


def test_cuenta_las_correcciones_previas_del_mismo_origen():
    ci = implementador.cadena.prompt_corregir("el CI falló.", "ci")
    revision = implementador.cadena.prompt_corregir("corregí.", "revision")
    assert implementador.correcciones_previas(ci, [ci, revision, ci]) == 1
    assert implementador.correcciones_previas(revision, [ci, revision, ci]) == 0
    assert implementador.correcciones_previas("<!-- cadena:pedido -->\nimplementá", [ci]) == 0


def test_sobran_las_carpetas_de_issues_sin_pr_abierto():
    nombres = ["issue-89", "issue-89-3", "issue-145", "issue-146-1", "registro.log", "otra"]
    assert implementador.carpetas_sobrantes(nombres, abiertos={145, 146}) == ["issue-89", "issue-89-3"]


def test_el_comentario_hecho_lleva_la_medida_de_codex():
    marca = implementador.medida_de_codex(4.25, 120345, "medium")
    assert marca == "<!-- implementador:codex minutos=4.2 tokens=120345 esfuerzo=medium -->"
