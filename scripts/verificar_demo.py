"""Verifica una demo pública ya desplegada (pasos 2, 4 y 5 de docs/demo-publica.md).

Uso:
    python scripts/verificar_demo.py https://gimnasio-pro.onrender.com

Gasta el cupo de la IP desde la que corre: esperá un minuto antes de repetirlo.
Quedan manuales el cupo por IP distinta con X-Forwarded-For y el reinicio programado.
"""

import json
import sys
import urllib.error
import urllib.request

SOLICITUDES_POR_MINUTO = 240
MAXIMO_BYTES = 1_000_000


def abrir_http(metodo, url, cuerpo=None):
    """Devuelve (estado, encabezados, texto) sin lanzar por códigos 4xx."""
    solicitud = urllib.request.Request(url, data=cuerpo, method=metodo)
    try:
        with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
            return respuesta.status, dict(respuesta.headers), respuesta.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8", "replace")


def verificar(base, abrir=abrir_http):
    """Devuelve la lista de fallas; vacía si la demo cumple."""
    base = base.rstrip("/")
    fallas = []

    estado, _, texto = abrir("GET", f"{base}/api/estado")
    try:
        modo_demo = json.loads(texto).get("modo_demo")
    except (json.JSONDecodeError, AttributeError):
        modo_demo = None
    if estado != 200 or modo_demo is not True:
        fallas.append(f"/api/estado: esperaba 200 con modo_demo true, llegó {estado} ({texto[:80]!r})")

    estado, _, _ = abrir("POST", f"{base}/api/estado", b"x" * (MAXIMO_BYTES + 1))
    if estado != 413:
        fallas.append(f"cuerpo de {MAXIMO_BYTES + 1} bytes: esperaba 413, llegó {estado}")

    # Ya se gastaron dos solicitudes del cupo; la 429 debe llegar antes de pasar la ventana completa.
    for _ in range(SOLICITUDES_POR_MINUTO):
        estado, encabezados, _ = abrir("GET", f"{base}/api/estado")
        if estado == 429:
            # Cloudflare entrega los encabezados en minúsculas.
            minusculas = {nombre.lower(): valor for nombre, valor in encabezados.items()}
            if not minusculas.get("retry-after", "").isdigit():
                fallas.append("429 sin Retry-After numérico")
            break
    else:
        fallas.append(f"{SOLICITUDES_POR_MINUTO} solicitudes más y no llegó el 429")
    return fallas


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    fallas = verificar(sys.argv[1])
    print("\n".join(fallas) if fallas else "La demo cumple los pasos 2, 4 y 5.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
