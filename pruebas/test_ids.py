from datetime import UTC, datetime, timedelta
from uuid import RFC_4122, UUID

import pytest

from gimnasio import crear_app
from gimnasio.comun import ids
from gimnasio.comun.ids import a_bytes, desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import RelojFijo


@pytest.fixture(autouse=True)
def reiniciar_secuencia(monkeypatch):
    monkeypatch.setattr(ids, "_ultimo_milisegundo", None)
    monkeypatch.setattr(ids, "_aleatorio", 0)


def test_formato_y_vector_de_la_rfc_9562(monkeypatch):
    # RFC 9562, apéndice A.6: mismo vector que en las pruebas JS.
    reloj = RelojFijo(datetime(2022, 2, 22, 19, 22, 22, tzinfo=UTC))
    aleatorio = (0xCC3 << 62) | 0x18C4DC0C0C07398F
    llamadas = []

    def bits(cantidad):
        llamadas.append(cantidad)
        return aleatorio

    monkeypatch.setattr(ids.secrets, "randbits", bits)
    identificador = nuevo_id(reloj)
    assert str(identificador) == "017f22e2-79b0-7cc3-98c4-dc0c0c07398f"
    assert identificador.version == 7
    assert identificador.variant == RFC_4122
    assert identificador.int >> 80 == 1645557742000
    assert llamadas == [74]


def test_ids_del_mismo_milisegundo_y_de_milisegundos_sucesivos_se_ordenan():
    reloj = RelojFijo(datetime(2026, 10, 26, tzinfo=UTC))
    identificadores = [nuevo_id(reloj) for _ in range(1000)]
    for _ in range(10):
        reloj.avanzar(timedelta(milliseconds=1))
        identificadores.append(nuevo_id(reloj))
    assert len(set(identificadores)) == len(identificadores)
    assert identificadores == sorted(identificadores)
    assert [str(i) for i in identificadores] == sorted(str(i) for i in identificadores)
    assert [a_bytes(i) for i in identificadores] == sorted(a_bytes(i) for i in identificadores)
    assert all(i.version == 7 and i.variant == RFC_4122 for i in identificadores)
    assert (identificadores[-1].int >> 80) - (identificadores[0].int >> 80) == 10


def test_usa_el_reloj_inyectado_en_la_app():
    reloj = RelojFijo(datetime(2022, 2, 22, 19, 22, 22, tzinfo=UTC))
    app = crear_app({"ENTORNO": "prueba"}, reloj=reloj)
    with app.app_context():
        assert nuevo_id().int >> 80 == 1645557742000


def test_conversiones_conservan_los_16_bytes_y_el_texto():
    identificador = desde_texto("017F22E2-79B0-7CC3-98C4-DC0C0C07398F")
    datos = bytes.fromhex("017f22e279b07cc398c4dc0c0c07398f")
    assert a_bytes(identificador) == datos
    assert desde_bytes(datos) == identificador
    assert desde_texto(str(identificador)) == identificador


@pytest.mark.parametrize(
    "texto",
    [
        "no-es-un-uuid",
        "017f22e2-79b0-4cc3-98c4-dc0c0c07398f",
        "017f22e2-79b0-7cc3-18c4-dc0c0c07398f",
    ],
)
def test_rechaza_textos_invalidos_versiones_y_variantes(texto):
    with pytest.raises(ValueError):
        desde_texto(texto)


def test_rechaza_bytes_invalidos_y_otros_uuid():
    with pytest.raises(ValueError):
        desde_bytes(b"corto")
    otro = UUID("017f22e2-79b0-4cc3-98c4-dc0c0c07398f")
    with pytest.raises(ValueError, match="UUIDv7"):
        desde_bytes(otro.bytes)
    with pytest.raises(ValueError, match="UUIDv7"):
        a_bytes(otro)


def test_el_acarreo_no_cambia_la_version_ni_la_variante(monkeypatch):
    monkeypatch.setattr(ids.secrets, "randbits", lambda cantidad: (1 << 62) - 1)
    reloj = RelojFijo(datetime(2026, 10, 26, tzinfo=UTC))
    primero, segundo = nuevo_id(reloj), nuevo_id(reloj)
    assert primero < segundo
    assert segundo.version == 7 and segundo.variant == RFC_4122
    assert segundo.int & ((1 << 62) - 1) == 0
    assert (segundo.int >> 64) & 0xFFF == 1


def test_al_agotarse_los_bits_no_se_repite_ni_se_desborda_el_uuid(monkeypatch):
    monkeypatch.setattr(ids.secrets, "randbits", lambda cantidad: (1 << 74) - 1)
    reloj = RelojFijo(datetime(2026, 10, 26, tzinfo=UTC))
    primero = nuevo_id(reloj)
    with pytest.raises(OverflowError):
        nuevo_id(reloj)
    reloj.avanzar(timedelta(milliseconds=1))
    assert nuevo_id(reloj) > primero


def test_trunca_las_fracciones_de_milisegundo_sin_redondear():
    reloj = RelojFijo(datetime(1970, 1, 1, microsecond=1999, tzinfo=UTC))
    assert nuevo_id(reloj).int >> 80 == 1


def test_rechaza_fechas_anteriores_a_la_epoca():
    with pytest.raises(ValueError, match="48 bits"):
        nuevo_id(RelojFijo(datetime(1969, 12, 31, tzinfo=UTC)))
