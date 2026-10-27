from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from gimnasio import crear_app
from gimnasio.comun.reloj import RelojFijo, RelojSistema, fecha_local, inicio_de_semana, reloj_actual


def test_fecha_local_y_semana_al_cruzar_medianoche_en_asuncion():
    reloj = RelojFijo(datetime(2026, 10, 26, 2, 59, 59, tzinfo=UTC))
    assert fecha_local(reloj.ahora()) == date(2026, 10, 25)
    assert inicio_de_semana(fecha_local(reloj.ahora())) == date(2026, 10, 19)
    reloj.avanzar(timedelta(seconds=1))
    assert fecha_local(reloj.ahora()) == date(2026, 10, 26)
    assert inicio_de_semana(fecha_local(reloj.ahora())) == date(2026, 10, 26)


@pytest.mark.parametrize("dias", range(7))
def test_la_semana_empieza_el_lunes_incluso_al_cambiar_de_mes(dias):
    fecha = date(2026, 10, 26) + timedelta(days=dias)
    assert inicio_de_semana(fecha) == date(2026, 10, 26)


def test_el_reloj_fijo_normaliza_a_utc_y_se_puede_fijar_de_nuevo():
    reloj = RelojFijo(datetime(2026, 10, 25, 23, tzinfo=timezone(timedelta(hours=-3))))
    assert reloj.ahora() == datetime(2026, 10, 26, 2, tzinfo=UTC)
    assert reloj.ahora().tzinfo is UTC
    reloj.fijar(datetime(2026, 11, 1, tzinfo=UTC))
    assert reloj.ahora() == datetime(2026, 11, 1, tzinfo=UTC)


def test_fecha_local_acepta_otra_zona():
    reloj = RelojFijo(datetime(2026, 10, 26, 2, tzinfo=UTC))
    assert fecha_local(reloj.ahora(), ZoneInfo("UTC")) == date(2026, 10, 26)


def test_el_reloj_y_fecha_local_rechazan_momentos_sin_zona():
    momento = datetime(2026, 10, 26)
    with pytest.raises(ValueError, match="zona horaria"):
        RelojFijo(momento)
    reloj = RelojFijo(momento.replace(tzinfo=UTC))
    with pytest.raises(ValueError, match="zona horaria"):
        reloj.fijar(momento)
    assert reloj.ahora().tzinfo is UTC
    with pytest.raises(ValueError, match="zona horaria"):
        fecha_local(momento)


def test_la_app_usa_el_reloj_del_sistema_por_defecto():
    app = crear_app({"ENTORNO": "prueba"})
    with app.app_context():
        assert isinstance(reloj_actual(), RelojSistema)
        momento = reloj_actual().ahora()
    assert momento.tzinfo is UTC
    assert momento.utcoffset() == timedelta(0)


def test_el_reloj_actual_es_el_inyectado_en_cada_app():
    primero = RelojFijo(datetime(2026, 10, 26, tzinfo=UTC))
    segundo = RelojFijo(datetime(2026, 11, 1, tzinfo=UTC))
    app = crear_app({"ENTORNO": "prueba"}, reloj=primero)
    otra_app = crear_app({"ENTORNO": "prueba"}, reloj=segundo)
    with app.app_context():
        assert reloj_actual() is primero
        with otra_app.app_context():
            assert reloj_actual() is segundo
        assert reloj_actual() is primero
