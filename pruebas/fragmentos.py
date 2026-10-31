"""Reparto de las pruebas en fragmentos para el CI (ver `pytest_collection_modifyitems` en conftest.py)."""

import zlib


def fragmento_de(nodeid, total):
    """El fragmento (1..total) que corre esta prueba: un hash estable, igual en cada proceso y en cada máquina."""
    return zlib.crc32(nodeid.encode("utf-8")) % total + 1
