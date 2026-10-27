"""Carga determinista de personas ficticias; claves e identificadores se generan de nuevo."""

import random
import secrets

from gimnasio.comun.bd import transaccion
from gimnasio.comun.formatos import normalizar_cedula, normalizar_telefono
from gimnasio.comun.ids import nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.demo import repositorio
from gimnasio.demo.nombres import APELLIDOS, NOMBRES
from gimnasio.permisos import servicio as permisos

USUARIOS_DEMO = (
    ("Lucía", "Benítez", "socio"),
    ("Rocío", "Ayala", "recepcion"),
    ("Marcos", "Giménez", "entrenador"),
    ("Ana", "Duarte", "administracion"),
)
SOCIOS_ADICIONALES = 36


def generar_personas():
    """Los datos públicos se repiten sin depender de las claves ni del generador aleatorio global."""
    aleatorio = random.Random(2026)
    cantidad = len(USUARIOS_DEMO) + SOCIOS_ADICIONALES
    cedulas = aleatorio.sample(range(9_900_000, 10_000_000), cantidad)
    telefonos = aleatorio.sample(range(10_000_000), cantidad)
    nombres = list(USUARIOS_DEMO)
    nombres.extend((aleatorio.choice(NOMBRES), aleatorio.choice(APELLIDOS), "socio") for _ in range(SOCIOS_ADICIONALES))
    return [
        {
            "nombre": nombre,
            "apellido": apellido,
            "cedula": normalizar_cedula(str(cedulas[indice])),
            "telefono": normalizar_telefono(f"+595 99{telefonos[indice]:07d}"),
            "correo": f"persona{indice + 1}@demo.gimnasio.invalid",
            "rol": rol,
            "es_demo": indice < len(USUARIOS_DEMO),
        }
        for indice, (nombre, apellido, rol) in enumerate(nombres)
    ]


def reiniciar():
    """Reemplaza todos los datos en una transacción; requiere las migraciones ya aplicadas."""
    reloj = reloj_actual()
    ahora = reloj.ahora()
    personas = generar_personas()
    socios = []
    with transaccion() as cursor:
        repositorio.vaciar_datos(cursor)
        repositorio.insertar_sede(cursor, nuevo_id(reloj), ahora)
        for persona in personas:
            # La clave se descarta: nunca se imprime ni depende de random.Random(2026).
            usuario_id = permisos.crear_usuario(
                cursor, persona, persona["rol"], clave=secrets.token_urlsafe(32), es_demo=persona["es_demo"]
            )
            if persona["rol"] == "socio":
                socios.append(usuario_id)
            elif persona["rol"] == "entrenador":
                entrenador_id = usuario_id
        for socio_id in socios:
            repositorio.insertar_asignacion(cursor, nuevo_id(reloj), socio_id, entrenador_id, ahora)
        # 37 socios: el 80 % se redondea al entero más cercano (30).
        for socio_id in socios[: round(len(socios) * 0.8)]:
            permisos.registrar_consentimiento(cursor, socio_id, "salud", True, "demo-1", socio_id)
