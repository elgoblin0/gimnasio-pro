"""Vectores de Paraguay compartidos con las pruebas de JavaScript."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from gimnasio.comun import formatos


@pytest.mark.parametrize(
    "entrada,salida",
    [
        (" SOCIO@ejemplo.test ", "socio@ejemplo.test"),
        ("nombre.apellido+gym@ejemplo.test", "nombre.apellido+gym@ejemplo.test"),
    ],
)
def test_normalizar_correo(entrada, salida):
    assert formatos.normalizar_correo(entrada) == salida


@pytest.mark.parametrize(
    "entrada",
    [None, 123, "", "sin-arroba", "a@@ejemplo.test", "a b@ejemplo.test", "a@ejemplo", "a" * 161 + "@ejemplo.test"],
)
def test_correo_invalido(entrada):
    with pytest.raises(ValueError):
        formatos.normalizar_correo(entrada)


VECTORES = json.loads((Path(__file__).parent / "vectores" / "formatos.json").read_text(encoding="utf-8"))
CASOS = [(nombre, caso) for nombre, casos in VECTORES.items() for caso in casos]


@pytest.mark.parametrize("nombre,caso", CASOS, ids=[f"{nombre}-{i}" for i, (nombre, _) in enumerate(CASOS)])
def test_vectores_compartidos(nombre, caso):
    def ejecutar():
        entrada = caso["entrada"]
        if nombre == "formatear_fecha":
            entrada = date.fromisoformat(entrada)
        elif nombre == "formatear_fecha_hora":
            entrada = datetime.fromisoformat(entrada)
        argumentos = [entrada]
        if "zona" in caso:
            argumentos.append(caso["zona"])
        return getattr(formatos, nombre)(*argumentos)

    if caso.get("error"):
        with pytest.raises(ValueError):
            ejecutar()
    else:
        assert ejecutar() == caso["salida"]


def test_cada_funcion_tiene_ocho_vectores_e_invalidos():
    assert set(VECTORES) == {
        "formatear_guaranies",
        "parsear_guaranies",
        "normalizar_cedula",
        "formatear_cedula",
        "normalizar_telefono",
        "formatear_telefono",
        "formatear_fecha",
        "formatear_fecha_hora",
    }
    for casos in VECTORES.values():
        assert len(casos) >= 8
        assert any(caso.get("error") for caso in casos)
        assert any("salida" in caso for caso in casos)


def test_formatear_fecha_rechaza_otros_tipos():
    for entrada in (None, "2026-10-27", datetime(2026, 10, 27)):
        with pytest.raises(ValueError):
            formatos.formatear_fecha(entrada)


def test_formatear_fecha_hora_rechaza_otros_tipos():
    for entrada in (None, "2026-10-27T12:00:00Z", date(2026, 10, 27)):
        with pytest.raises(ValueError):
            formatos.formatear_fecha_hora(entrada)
