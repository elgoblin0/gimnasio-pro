"""Una prueba por celda de la matriz (ADR 0006). La tabla esperada se escribe aparte a propósito:
cambiar un permiso obliga a cambiar las dos y a pasar por la revisión de Opus."""

import pytest

from gimnasio.permisos.matriz import PERMISOS, ROLES, puede
from gimnasio.permisos.servicio import requiere

S, R, E, A = "socio", "recepcion", "entrenador", "administracion"
ESPERADO = {
    "entrenamiento.registrar_propio": {S},
    "salud.ver_propia": {S},
    "consentimientos.gestionar_propios": {S},
    "visitas.registrar": {R},
    "socios.ver_tarjeta": {R, A},
    "pagos.registrar": {R, A},
    "clases.gestionar_reservas": {R},
    "socios.ver_asignados": {E},
    "salud.ver_asignados": {E},
    "programas.editar": {E},
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


def test_rechaza_roles_y_permisos_desconocidos():
    with pytest.raises(ValueError):
        puede("invitado", "visitas.registrar")
    with pytest.raises(ValueError):
        puede(S, "todo.hacer")
    with pytest.raises(ValueError):
        requiere("todo.hacer")
