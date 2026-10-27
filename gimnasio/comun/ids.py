"""UUIDv7 con secuencia local dentro del mismo milisegundo (RFC 9562, 6.2)."""

import secrets
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID

from gimnasio.comun.reloj import Reloj, reloj_actual

_EPOCA = datetime(1970, 1, 1, tzinfo=UTC)
_MILISEGUNDO = timedelta(milliseconds=1)
_MASCARA_62 = (1 << 62) - 1
_cerrojo = Lock()
_ultimo_milisegundo = None
_aleatorio = 0


def nuevo_id(reloj: Reloj | None = None) -> UUID:
    """Usa el reloj de la app por defecto; el orden se garantiza por proceso.

    Un cambio de milisegundo reinicia los 74 bits aleatorios. Si se fija el
    reloj hacia atrás, el identificador vuelve a reflejar ese momento.
    """
    global _ultimo_milisegundo, _aleatorio
    fuente = reloj if reloj is not None else reloj_actual()
    with _cerrojo:
        momento = fuente.ahora()
        if momento.utcoffset() is None:
            raise ValueError("El momento debe incluir una zona horaria")
        milisegundo = (momento - _EPOCA) // _MILISEGUNDO
        if not 0 <= milisegundo < 1 << 48:
            raise ValueError("El momento debe caber en los 48 bits de milisegundos del UUIDv7")
        aleatorio = _aleatorio + 1 if milisegundo == _ultimo_milisegundo else secrets.randbits(74)
        if aleatorio >= 1 << 74:
            raise OverflowError("Se agotaron los UUIDv7 del milisegundo actual")
        _ultimo_milisegundo, _aleatorio = milisegundo, aleatorio
        valor = (milisegundo << 80) | (7 << 76) | ((aleatorio >> 62) << 64) | (2 << 62) | (aleatorio & _MASCARA_62)
        return UUID(int=valor)


def _validar(identificador: UUID) -> UUID:
    if identificador.version != 7:
        raise ValueError("El identificador debe ser un UUIDv7")
    return identificador


def a_bytes(identificador: UUID) -> bytes:
    return _validar(identificador).bytes


def desde_bytes(datos: bytes) -> UUID:
    return _validar(UUID(bytes=datos))


def desde_texto(texto: str) -> UUID:
    return _validar(UUID(texto))
