"""Pruebas de la lógica pura de la cadena de agentes (sin gh ni red)."""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar(nombre):
    especificacion = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


cadena = cargar("cadena")


def test_lee_las_dependencias_del_formato_de_la_plantilla():
    assert cadena.dependencias("Objetivo\n\nDepende de: #12, #13\n") == [12, 13]
    assert cadena.dependencias("Sin dependencias") == []
    assert cadena.dependencias(None) == []


def test_elige_el_issue_listo_mas_bajo_con_dependencias_cerradas():
    issues = [
        {"number": 30, "body": ""},
        {"number": 21, "body": "Depende de: #20"},
        {"number": 25, "body": "Depende de: #19"},
    ]
    cerrados = {19}
    assert cadena.elegir_siguiente(issues, cerrados.__contains__)["number"] == 25
    assert cadena.elegir_siguiente([{"number": 21, "body": "Depende de: #20"}], cerrados.__contains__) is None


def test_solo_las_ramas_de_la_cadena_tienen_numero_de_issue():
    assert cadena.numero_de_rama("codex/issue-42") == 42
    assert cadena.numero_de_rama("automatiza-cadena-agentes") is None


def test_detecta_las_rutas_sensibles_de_agents():
    assert cadena.es_sensible(["gimnasio/reglas/motor.py"])
    assert cadena.es_sensible(["docs/x.md", "migraciones/0012_algo.sql"])
    assert cadena.es_sensible(["gimnasio/comun/migrar.py"])
    assert not cadena.es_sensible(["gimnasio/comun/reloj.py", "gimnasio/static/js/app.js"])


def test_una_revision_sin_comentarios_en_linea_aprueba():
    assert cadena.revision_aprobada("Codex Review: hallazgos", 0)
    assert cadena.revision_aprobada("Codex Review: Didn't find any major issues. 🎉", 2)
    assert not cadena.revision_aprobada("P1: falta la prueba", 1)


def test_reconoce_la_duda_de_codex():
    texto = "Leí el issue.\nNECESITA-CRITERIO: ¿la visita cuenta si dura menos de 5 minutos? Recomiendo que no.\n"
    assert cadena.pregunta_de_criterio(texto).startswith("¿la visita cuenta")
    assert cadena.pregunta_de_criterio("Listo, subí los cambios.") is None


def test_un_pr_sensible_espera_la_revision_de_opus():
    assert cadena.lista_para_fusionar({"revisado:codex"}, ["gimnasio/socio/rutas.py"])
    assert not cadena.lista_para_fusionar({"revisado:codex"}, ["gimnasio/reglas/motor.py"])
    assert cadena.lista_para_fusionar({"revisado:codex", "revisado:opus"}, ["gimnasio/reglas/motor.py"])
    assert not cadena.lista_para_fusionar({"revisado:opus"}, ["gimnasio/socio/rutas.py"])


def test_un_pr_sin_archivos_nunca_se_fusiona():
    assert not cadena.lista_para_fusionar({"revisado:codex", "revisado:opus"}, [])


def test_el_pedido_de_implementar_incluye_el_issue_y_la_salida_de_criterio():
    texto = cadena.prompt_implementar({"number": 7, "title": "Alta de socio", "body": "Objetivo: X"})
    assert cadena.MARCA_PEDIDO in texto and f"{cadena.ENCABEZADO_LOCAL} implementá el issue #7" in texto
    assert "@codex" not in texto
    assert "NECESITA-CRITERIO:" in texto
    assert "Objetivo: X" in texto


def test_los_pedidos_de_correccion_llevan_la_marca_que_cuenta_intentos():
    texto = cadena.prompt_corregir("el CI falló.", "ci")
    assert cadena.MARCA_CORREGIR in texto and cadena.MARCA_ORIGEN.format(origen="ci") in texto


def test_cada_origen_de_correccion_tiene_su_propio_tope():
    """En #135 una corrección de Opus agotó el tope compartido y el PR quedó bloqueado dos horas."""
    comentarios = [
        cadena.prompt_corregir("el CI falló.", "ci"),
        cadena.prompt_corregir("corregí los hallazgos.", "revision"),
        cadena.prompt_corregir("atendé a Opus.", "opus"),
        "<!-- cadena:corregir -->\nPedido de antes, sin origen",
    ]
    assert cadena.correcciones_pedidas(comentarios, "ci") == 1
    assert cadena.correcciones_pedidas(comentarios, "revision") == 1
    assert cadena.correcciones_pedidas(comentarios, "conflicto") == 0
    assert set(cadena.MAX_CORRECCIONES) == {"ci", "revision", "opus", "conflicto"}


def test_elige_un_segundo_issue_solo_si_no_comparte_modulo_con_los_en_curso():
    issues = [
        {"number": 146, "body": "", "labels": [{"name": "modulo:visitas"}, {"name": "modulo:permisos"}]},
        {"number": 147, "body": "", "labels": [{"name": "modulo:reglas"}]},
        {"number": 148, "body": "", "labels": [{"name": "tipo:funcion"}]},
    ]
    en_curso = [{"modulo:migraciones", "modulo:demo"}]
    assert cadena.elegir_siguiente(issues, lambda n: True, en_curso)["number"] == 146
    en_curso = [{"modulo:visitas"}]
    assert cadena.elegir_siguiente(issues, lambda n: True, en_curso)["number"] == 147
    # Sin módulo no se sabe qué toca: no corre en paralelo con nada.
    assert cadena.elegir_siguiente(issues[2:], lambda n: True, [{"modulo:reglas"}]) is None
    assert cadena.elegir_siguiente(issues[1:2], lambda n: True, [{"tipo:funcion"}]) is None


def test_la_rama_vacia_no_dispara_el_ci_y_la_fusion_no_hereda_su_mensaje():
    """El squash copia los mensajes de los commits: `[skip ci]` en main saltaría su CI."""
    assert "[skip ci]" in cadena.mensaje_rama_vacia("codex/issue-7")
    assert "[skip ci]" not in cadena.cuerpo_de_fusion("")
    assert cadena.cuerpo_de_fusion("Closes #7\n\nNotas") == "Closes #7\n\nNotas"
    assert "[skip ci]" not in cadena.cuerpo_de_fusion("Closes #7 [skip ci]")


def test_un_pr_de_adr_solo_toca_docs_adr_y_glosario():
    assert cadena.es_solo_adr(["docs/adr/0017-tema.md", "GLOSSARY.md"])
    assert not cadena.es_solo_adr(["docs/adr/0017-tema.md", "gimnasio/reglas/progresion.py"])
    assert not cadena.es_solo_adr([])


def test_un_issue_cerrado_pierde_las_etiquetas_de_estado():
    assert cadena.etiquetas_de_estado_a_quitar({"estado:en-curso", "agente:codex", "estado:revision"}) == [
        "estado:en-curso",
        "estado:revision",
    ]
    assert cadena.etiquetas_de_estado_a_quitar({"tipo:funcion", "modulo:visitas"}) == []


def test_el_pedido_menciona_a_codex_solo_si_se_lo_pide(monkeypatch):
    issue = {"number": 7, "title": "Alta", "body": "X"}
    monkeypatch.setenv("CADENA_MENCIONAR_CODEX", "1")
    assert "@codex implementá el issue #7" in cadena.prompt_implementar(issue)
    assert "@codex el CI falló." in cadena.prompt_corregir("el CI falló.", "ci")
    monkeypatch.delenv("CADENA_MENCIONAR_CODEX")
    assert "@codex" not in cadena.prompt_corregir("el CI falló.", "ci")


def comentario(cuerpo, minuto, ojos=0):
    return {"body": cuerpo, "created_at": f"2026-10-29T10:{minuto:02d}:00Z", "reactions": {"eyes": ojos}}


PEDIDO = f"{cadena.MARCA_PEDIDO}\nimplementá el issue #7"
AHORA = cadena.fecha("2026-10-29T11:30:00Z")


def test_un_pedido_cerrado_con_hecho_no_espera():
    assert cadena.pedido_en_espera([comentario(PEDIDO, 0), comentario(f"{cadena.MARCA_HECHO}\nlisto", 5)]) is None
    assert cadena.pedido_en_espera([comentario(PEDIDO, 0)])["body"] == PEDIDO


def test_avisa_si_nadie_toma_el_pedido_y_el_implementador_esta_libre():
    pedido = cadena.pedido_en_espera([comentario(PEDIDO, 50)])
    assert cadena.demora(pedido, AHORA, ocupado=False) == "sin-tomar"
    assert cadena.demora(pedido, AHORA, ocupado=True) is None  # atiende otro PR: esperar es normal
    reciente = cadena.pedido_en_espera([comentario(PEDIDO, 20)])
    assert cadena.demora(reciente, cadena.fecha("2026-10-29T10:30:00Z"), ocupado=False) is None


def test_avisa_si_el_pedido_tomado_no_termina():
    tomado = cadena.pedido_en_espera([comentario(PEDIDO, 0, ojos=1)])
    assert cadena.demora(tomado, AHORA, ocupado=True) == "colgado"
    assert cadena.demora(tomado, cadena.fecha("2026-10-29T11:00:00Z"), ocupado=True) is None
    # Un fallo reinicia la cuenta: el implementador reintenta.
    con_fallo = cadena.pedido_en_espera([comentario(PEDIDO, 0, ojos=1), comentario(cadena.MARCA_FALLO, 59)])
    assert cadena.demora(con_fallo, AHORA, ocupado=True) is None


def test_avisa_una_sola_vez_por_pedido():
    avisado = cadena.pedido_en_espera([comentario(PEDIDO, 0), comentario(f"{cadena.MARCA_AVISO}\nnadie lo tomó", 20)])
    assert cadena.demora(avisado, AHORA, ocupado=False) is None


def test_la_etapa_termina_cuando_no_quedan_issues_de_codex_abiertos():
    cierres = [{"number": 141, "title": "Especificación: Etapa 3"}, {"number": 154, "title": "Cierre de etapa 3"}]
    assert cadena.issue_de_cierre(cierres)["number"] == 154
    assert cadena.issue_de_cierre(cierres[:1]) is None
