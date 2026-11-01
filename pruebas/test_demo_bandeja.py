"""Estados de la bandeja presentes al reiniciar la demo, sobre MySQL."""

import pytest

from gimnasio.comun.bd import conexion_actual, transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.demo.servicio import reiniciar
from gimnasio.entrenador.servicio import consultar_bandeja, consultar_socio, listar_socios
from gimnasio.entrenamiento.servicio import consultar_propuesta
from gimnasio.programas.servicio import listar_equipos

pytestmark = pytest.mark.bd


def test_bandeja_cubre_estados_y_se_repite(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE rol='entrenador' AND es_demo=TRUE")
            marcos = {"id": str(desde_bytes(cursor.fetchone()["id"])), "rol": "entrenador"}
        primera = consultar_bandeja(marcos)
        # La semilla no revoca ningún consentimiento: ese grupo queda vacío.
        assert all(grupo["socios"] for grupo in primera["grupos"] if grupo["tipo"] != "sin_consentimiento_salud")
        asignados = listar_socios(marcos)
        with transaccion() as cursor:
            cursor.execute(
                "SELECT u.id,p.correo FROM usuarios u JOIN personas p ON p.id=u.persona_id "
                "WHERE p.correo LIKE 'bandeja%@demo.gimnasio.invalid'"
            )
            nuevos = [{"id": str(desde_bytes(s["id"])), "correo": s["correo"]} for s in cursor.fetchall()]
        assert len(nuevos) == 8
        assert {s["id"] for s in nuevos} <= {s["id"] for s in asignados}
        por_correo = {s["correo"].split("@")[0]: s for s in nuevos}
        motivos = {s["id"]: s["motivos"] for g in primera["grupos"] for s in g["socios"]}
        for indice, tipo in enumerate(
            (
                "aviso_seguridad",
                "aviso_seguridad",
                "sin_programa",
                "secuencia_terminada",
                "ejercicio_sin_alternativa",
                "aviso_progresion",
            ),
            1,
        ):
            assert [m["tipo"] for m in motivos[por_correo[f"bandeja{indice}"]["id"]]] == [tipo]
        for indice in (7, 8):
            assert por_correo[f"bandeja{indice}"]["id"] not in motivos
        for indice, freno in (
            (1, "dolor_reportado"),
            (2, "restriccion_salud"),
            (6, "chequeo_desfavorable"),
            (7, "dolor_reportado"),
        ):
            vista = consultar_socio(por_correo[f"bandeja{indice}"]["id"], marcos)
            assert [a["freno"] for a in vista["avisos"]] == [freno]
            assert vista["avisos"][0]["revisado"] == (indice == 7)
        equipos = [e for e in listar_equipos() if e["estado"] == "fuera_de_servicio"]
        assert len(equipos) == 2
        alternativa = consultar_propuesta(por_correo["bandeja8"]["id"], marcos, sin_chequeo=True)
        assert alternativa["ejercicios"]
        assert all(not e["no_disponible"] for e in alternativa["ejercicios"])
        assert all(e["ejercicio_hecho_id"] != e["ejercicio_id"] for e in alternativa["ejercicios"])
        reiniciar()
        assert consultar_bandeja(marcos) == primera
        assert listar_socios(marcos) == asignados


def test_bandeja_acota_las_consultas_a_la_base(app_con_bd):
    """Contra una base remota cada consulta cuesta decenas de milisegundos: en local no se nota."""
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE rol='entrenador' AND es_demo=TRUE")
            marcos = {"id": str(desde_bytes(cursor.fetchone()["id"])), "rol": "entrenador"}

        def consultas():
            cursor = conexion_actual().cursor()
            cursor.execute("SHOW SESSION STATUS LIKE 'Questions'")
            total = int(cursor.fetchone()[1])
            cursor.close()
            return total

        antes = consultas()
        bandeja = consultar_bandeja(marcos)
        hechas = consultas() - antes - 1
        assert sum(len(grupo["socios"]) for grupo in bandeja["grupos"]) > 80
        assert hechas <= 110
