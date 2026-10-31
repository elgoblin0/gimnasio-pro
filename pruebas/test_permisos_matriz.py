"""Una prueba por celda de la matriz (ADR 0006). La tabla esperada se escribe aparte a propósito:
cambiar un permiso obliga a cambiar las dos y a pasar por la revisión de Opus."""

import pytest

from gimnasio import crear_app
from gimnasio.permisos import servicio
from gimnasio.permisos.matriz import PERMISOS, ROLES, puede
from gimnasio.permisos.servicio import requiere

S, R, E, A = "socio", "recepcion", "entrenador", "administracion"
ESPERADO = {
    "socios.editar_datos_propios": {S},
    "socios.editar_datos": {R, A},
    "entrenamiento.ver_propio": {S},
    "entrenamiento.registrar_propio": {S},
    "salud.ver_propia": {S},
    "consentimientos.gestionar_propios": {S},
    "visitas.registrar": {R},
    "visitas.ver": {R},
    "ocupacion.ver": {S, R, E, A},
    "socios.ver_tarjeta": {R, A},
    "pagos.registrar": {R, A},
    "clases.gestionar_reservas": {R},
    "socios.ver_asignados": {E},
    "avisos.revisar": {E},
    "entrenamiento.ver_asignados": {E},
    "salud.ver_asignados": {E},
    "programas.editar": {E},
    "alternativas.editar": {E, A},
    "equipos.gestionar": {E, A},
    "configuracion.editar": {A},
    "usuarios.administrar": {A},
}


def test_la_tabla_esperada_cubre_toda_la_matriz():
    assert set(ESPERADO) == set(PERMISOS)


@pytest.mark.parametrize("rol", ROLES)
@pytest.mark.parametrize("permiso", sorted(ESPERADO))
def test_celda(rol, permiso):
    assert puede(rol, permiso) is (rol in ESPERADO[permiso])


def test_salud_nunca_la_ven_recepcion_ni_administracion():
    for permiso in ("salud.ver_propia", "salud.ver_asignados"):
        assert not puede(R, permiso)
        assert not puede(A, permiso)


def test_recepcion_no_puede_leer_restricciones_de_salud():
    assert not puede(R, "salud.ver_propia")
    assert not puede(R, "salud.ver_asignados")


@pytest.mark.parametrize("rol", [None, *ROLES])
@pytest.mark.parametrize(
    "permiso,rol_permitido",
    [("entrenamiento.ver_propio", S), ("entrenamiento.ver_asignados", E), ("visitas.ver", R)],
)
def test_requiere_en_lecturas_del_recorrido(monkeypatch, rol, permiso, rol_permitido):
    app = crear_app({"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas", "MODO_DEMO": False})
    monkeypatch.setattr(servicio, "usuario_actual", lambda: {"rol": rol} if rol else None)

    @app.get("/api/prueba/lectura")
    @requiere(permiso)
    def lectura():
        return "", 204

    respuesta = app.test_client().get("/api/prueba/lectura")
    esperado = 401 if rol is None else 204 if rol == rol_permitido else 403
    assert respuesta.status_code == esperado
    if esperado != 204:
        assert respuesta.get_json()["error"]["codigo"] == ("sin_sesion" if rol is None else "sin_permiso")


def test_rechaza_roles_y_permisos_desconocidos():
    with pytest.raises(ValueError):
        puede("invitado", "visitas.registrar")
    with pytest.raises(ValueError):
        puede(S, "todo.hacer")
    with pytest.raises(ValueError):
        requiere("todo.hacer")


@pytest.mark.parametrize("rol,estado", [(None, 401), (S, 403), (R, 403), (E, 204), (A, 204)])
def test_catalogo_admite_cualquiera_de_los_dos_permisos(monkeypatch, rol, estado):
    app = crear_app({"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas"})
    monkeypatch.setattr(servicio, "usuario_actual", lambda: {"rol": rol} if rol else None)
    # Hace independientes los permisos para comprobar las dos vías de acceso.
    monkeypatch.setitem(PERMISOS, "alternativas.editar", {A})

    @app.get("/api/prueba/catalogo")
    @requiere("alternativas.editar", "programas.editar")
    def catalogo():
        return "", 204

    assert app.test_client().get("/api/prueba/catalogo").status_code == estado
