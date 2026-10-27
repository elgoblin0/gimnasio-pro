"""Formatos y validaciones de Paraguay, sin acceso al reloj ni al dominio."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _agrupar_miles(digitos: str) -> str:
    return re.sub(r"(?<=[0-9])(?=(?:[0-9]{3})+$)", ".", digitos)


def formatear_guaranies(importe: int) -> str:
    """Muestra un importe entero con espacio normal y puntos de miles."""
    if not isinstance(importe, int) or isinstance(importe, bool):
        raise ValueError("El importe debe ser un entero")
    signo = "-" if importe < 0 else ""
    return f"{signo}₲ {_agrupar_miles(str(abs(importe)))}"


def parsear_guaranies(texto: str) -> int:
    """Acepta dígitos o miles agrupados, con símbolo opcional y sin decimales."""
    if not isinstance(texto, str):
        raise ValueError("El importe debe ser texto")
    coincidencia = re.fullmatch(r"(-?)(?:(?:₲|Gs\.) *)?([0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)", texto.strip())
    if coincidencia is None:
        raise ValueError("El importe debe estar en guaraníes sin decimales")
    signo, digitos = coincidencia.groups()
    return int(signo + digitos.replace(".", ""))


def normalizar_cedula(texto: str) -> str:
    """Conserva los dígitos, incluidos ceros iniciales, y valida su cantidad."""
    if not isinstance(texto, str) or re.fullmatch(r"[0-9. ]+", texto) is None:
        raise ValueError("La cédula solo admite dígitos, puntos y espacios")
    digitos = texto.replace(".", "").replace(" ", "")
    if not 5 <= len(digitos) <= 8:
        raise ValueError("La cédula debe tener de 5 a 8 dígitos")
    return digitos


def formatear_cedula(texto: str) -> str:
    return _agrupar_miles(normalizar_cedula(texto))


def normalizar_telefono(texto: str) -> str:
    """Valida un celular o fijo y devuelve el número internacional +595."""
    if not isinstance(texto, str) or re.fullmatch(r" *\+?[0-9 ()-]+", texto) is None:
        raise ValueError("El teléfono contiene caracteres inválidos")
    numero = re.sub(r"[ ()-]", "", texto)
    if numero.startswith("+"):
        if not numero.startswith("+595"):
            raise ValueError("El teléfono debe ser de Paraguay (+595)")
        nacional = numero[4:]
    elif numero.startswith("595") and len(numero) in (11, 12):
        nacional = numero[3:]
    else:
        nacional = numero.removeprefix("0")
    if re.fullmatch(r"(?:9[0-9]{8}|[2-8][0-9]{7,8})", nacional) is None:
        raise ValueError("El teléfono debe ser un celular o fijo de Paraguay")
    return "+595" + nacional


def formatear_telefono(texto: str) -> str:
    nacional = normalizar_telefono(texto)[4:]
    if nacional.startswith("9"):
        return f"+595 {nacional[:3]} {nacional[3:6]} {nacional[6:]}"
    return f"+595 {nacional[:2]} {nacional[2:]}"


def formatear_fecha(fecha: date) -> str:
    if not isinstance(fecha, date) or isinstance(fecha, datetime):
        raise ValueError("Se requiere una fecha sin hora")
    return f"{fecha.day:02d}/{fecha.month:02d}/{fecha.year:04d}"


def formatear_fecha_hora(fecha_hora: datetime, zona: str = "America/Asuncion") -> str:
    if not isinstance(fecha_hora, datetime) or fecha_hora.utcoffset() is None:
        raise ValueError("Se requiere una fecha y hora con zona horaria")
    if not isinstance(zona, str):
        raise ValueError("La zona horaria debe ser texto")
    try:
        local = fecha_hora.astimezone(ZoneInfo(zona))
    except ZoneInfoNotFoundError as error:
        raise ValueError("Zona horaria desconocida") from error
    return f"{formatear_fecha(local.date())} {local.hour:02d}:{local.minute:02d}"
