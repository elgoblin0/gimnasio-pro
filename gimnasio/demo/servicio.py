"""Recorrido ficticio reiniciable; identidades estables y credenciales opacas nuevas."""

import random
import secrets
from collections import OrderedDict, deque
from datetime import UTC, datetime, time, timedelta
from itertools import count
from math import ceil
from threading import Lock

from flask import current_app

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.formatos import normalizar_cedula, normalizar_telefono
from gimnasio.comun.ids import desde_texto
from gimnasio.comun.reloj import ZONA_SEDE, fecha_local, reloj_actual
from gimnasio.comun.tipos import ZONAS_CUERPO
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
SOCIOS_HISTORIAL = 40
HORARIO_SEDE = {str(dia): [["06:00", "22:00"]] for dia in range(1, 6)}
HORARIO_SEDE["6"] = [["08:00", "14:00"]]
SOLICITUDES_POR_MINUTO = 60
VENTANA_DE_SOLICITUDES = timedelta(minutes=1)


def id_ficticio(numero, momento):
    """UUIDv7 reproducible para igual reloj/semilla, validado por comun.ids."""
    if type(numero) is not int or not 0 < numero < 2**48:
        raise ValueError("El número de identidad ficticia debe ser un entero positivo de 48 bits.")
    if momento.utcoffset() is None:
        raise ValueError("El momento debe incluir una zona horaria.")
    milisegundos = (momento - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(milliseconds=1)
    if not 0 <= milisegundos < 2**48:
        raise ValueError("El momento debe caber en los 48 bits del UUIDv7.")
    fecha = f"{milisegundos:012x}"
    return desde_texto(f"{fecha[:8]}-{fecha[8:]}-7000-8000-{numero:012x}")


def _cargar_programas(cursor, socios, siguiente_id, ahora):
    fuerza, cardio = siguiente_id(), siguiente_id()
    alternativa_fuerza, alternativa_cardio = siguiente_id(), siguiente_id()
    zonas_fuerza = tuple(z for z in ZONAS_CUERPO if z in {"gluteos", "cuadriceps", "rodillas", "zona_lumbar"})
    zonas_cardio = tuple(z for z in ZONAS_CUERPO if z in {"cuadriceps", "pantorrillas"})
    for identificador, nombre, equipo in (
        (fuerza, "Sentadilla ficticia", "barra"),
        (alternativa_fuerza, "Sentadilla con mancuernas ficticia", "mancuernas"),
    ):
        repositorio.insertar_ejercicio(
            cursor,
            identificador,
            nombre,
            ["repeticiones", "carga"],
            ahora,
            patron_movimiento="sentadilla",
            equipo=equipo,
            incremento_carga="2.50",
            zonas=zonas_fuerza,
        )
    for identificador, nombre, equipo in (
        (cardio, "Caminata ficticia", "cinta"),
        (alternativa_cardio, "Caminata sin cinta ficticia", "sin equipo"),
    ):
        repositorio.insertar_ejercicio(
            cursor,
            identificador,
            nombre,
            ["duracion", "distancia"],
            ahora,
            patron_movimiento="marcha",
            equipo=equipo,
            zonas=zonas_cardio,
        )
    for original, alternativa in ((fuerza, alternativa_fuerza), (cardio, alternativa_cardio)):
        repositorio.insertar_alternativa(cursor, original, alternativa, 1)
        repositorio.insertar_alternativa(cursor, alternativa, original, 1)
    cajon = siguiente_id()
    repositorio.insertar_ejercicio(
        cursor,
        cajon,
        "Sentadilla en cajón ficticia",
        ["repeticiones", "carga"],
        ahora,
        patron_movimiento="sentadilla",
        equipo="cajon",
        incremento_carga="2.50",
        zonas=("gluteos", "cuadriceps"),
    )
    repositorio.insertar_alternativa(cursor, fuerza, cajon, 2)
    repositorio.insertar_alternativa(cursor, cajon, fuerza, 1)
    for socio_id in socios[:2]:
        programa, primera, segunda = siguiente_id(), siguiente_id(), siguiente_id()
        repositorio.insertar_programa(cursor, programa, socio_id, ahora)
        repositorio.insertar_sesion_planificada(cursor, primera, programa, 1, "Fuerza y cardio")
        repositorio.insertar_sesion_planificada(cursor, segunda, programa, 2, "Fuerza")
        ejercicio_fuerza = siguiente_id()
        repositorio.insertar_ejercicio_planificado(
            cursor,
            ejercicio_fuerza,
            primera,
            fuerza,
            1,
            2,
            repeticiones_minimas=8,
            repeticiones_maximas=12,
            rir_objetivo=2,
            descanso=90,
            carga="20.50",
        )
        repositorio.insertar_ejercicio_planificado(
            cursor,
            siguiente_id(),
            primera,
            cardio,
            2,
            1,
            rir_objetivo=2,
            descanso=60,
            duracion=120,
            distancia="1500.25",
        )
        repositorio.insertar_ejercicio_planificado(
            cursor,
            siguiente_id(),
            segunda,
            fuerza,
            1,
            2,
            repeticiones_minimas=8,
            repeticiones_maximas=12,
            rir_objetivo=2,
            descanso=90,
            carga="25.00",
        )
        if socio_id == socios[0]:
            repositorio.insertar_ejercicio_planificado(
                cursor,
                siguiente_id(),
                primera,
                alternativa_fuerza,
                3,
                2,
                repeticiones_minimas=8,
                repeticiones_maximas=12,
                rir_objetivo=2,
                descanso=90,
                carga="20.50",
            )
            # Tres semanas anteriores completas: no acreditan pendientes de las sesiones nuevas.
            for semana, repeticiones in enumerate((10, 11, 12), start=1):
                momento = ahora - timedelta(weeks=4 - semana)
                planificada, realizada = siguiente_id(), siguiente_id()
                repositorio.insertar_sesion_planificada(
                    cursor, planificada, programa, semana - 4, "Fuerza ficticia anterior"
                )
                for posicion, ejercicio, reps in ((1, fuerza, repeticiones), (2, alternativa_fuerza, repeticiones - 2)):
                    planificado = siguiente_id()
                    repositorio.insertar_ejercicio_planificado(
                        cursor,
                        planificado,
                        planificada,
                        ejercicio,
                        posicion,
                        2,
                        repeticiones_minimas=8,
                        repeticiones_maximas=12,
                        rir_objetivo=2,
                        descanso=90,
                        carga="20.50",
                    )
                    repositorio.insertar_historial(
                        cursor,
                        realizada,
                        (siguiente_id(), siguiente_id()),
                        socio_id,
                        planificada,
                        planificado,
                        momento,
                        reps,
                    )
        if socio_id == socios[1]:
            repositorio.insertar_parcial(
                cursor, siguiente_id(), siguiente_id(), socio_id, primera, ejercicio_fuerza, ahora
            )


class LimitePorIp:
    """Ventana móvil en memoria, compartida por los hilos de un único proceso de la demo."""

    def __init__(self):
        self.solicitudes = OrderedDict()
        self._candado = Lock()

    def espera(self, ip):
        """Admite la solicitud o devuelve los segundos hasta que haya lugar."""
        with self._candado:
            ahora = reloj_actual().ahora()
            vencimiento = ahora - VENTANA_DE_SOLICITUDES
            # El orden sigue la última solicitud admitida: las IP inactivas salen primero.
            while self.solicitudes:
                primeras = next(iter(self.solicitudes.values()))
                if primeras[-1] > vencimiento:
                    break
                self.solicitudes.popitem(last=False)
            solicitudes = self.solicitudes.setdefault(ip, deque())
            while solicitudes and solicitudes[0] <= vencimiento:
                solicitudes.popleft()
            if len(solicitudes) >= SOLICITUDES_POR_MINUTO:
                return ceil((solicitudes[0] + VENTANA_DE_SOLICITUDES - ahora).total_seconds())
            solicitudes.append(ahora)
            self.solicitudes.move_to_end(ip)
            return 0


def generar_personas():
    """Los datos públicos se repiten sin depender de las claves ni del generador aleatorio global."""
    aleatorio = random.Random(2026)
    cantidad = len(USUARIOS_DEMO) + SOCIOS_ADICIONALES
    cedulas = aleatorio.sample(range(9_900_000, 10_000_000), cantidad)
    telefonos = aleatorio.sample(range(10_000_000), cantidad)
    nombres = list(USUARIOS_DEMO)
    nombres.extend((aleatorio.choice(NOMBRES), aleatorio.choice(APELLIDOS), "socio") for _ in range(SOCIOS_ADICIONALES))
    personas = [
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

    # Se conserva la generación anterior para los accesos y los casos del recorrido.
    for indice in range(SOCIOS_HISTORIAL):
        personas.append(
            {
                "nombre": aleatorio.choice(NOMBRES),
                "apellido": aleatorio.choice(APELLIDOS),
                "cedula": str(98_000_000 + indice),
                "telefono": f"+595980{indice:06d}",
                "correo": f"historial{indice + 1}@demo.gimnasio.invalid",
                "rol": "socio",
                "es_demo": False,
            }
        )
    return personas


def generar_visitas(ahora, socios):
    """Ocho semanas anteriores al día local; a lo sumo una visita diaria por socio."""
    aleatorio = random.Random(ahora.isoformat())
    visitas = []
    hoy = fecha_local(ahora)
    for dias in range(56, 0, -1):
        fecha = hoy - timedelta(days=dias)
        if fecha.isoweekday() == 7:
            continue
        sabado = fecha.isoweekday() == 6
        presentes = aleatorio.sample(socios, 10 if sabado else 30)
        for indice, socio in enumerate(presentes):
            # La mayoría entra cerca de las 07:00 o entre las 18:00 y las 20:00.
            hora = 9 if sabado else (7 if indice < 10 else 18 if indice < 20 else 19 if indice < 28 else 14)
            entrada = datetime.combine(fecha, time(hora), ZONA_SEDE) + timedelta(minutes=aleatorio.randrange(60))
            duracion = round(aleatorio.triangular(40, 110, 60))
            visitas.append((socio, entrada.astimezone(UTC), (entrada + timedelta(minutes=duracion)).astimezone(UTC)))
    return visitas


def reiniciar():
    """Reemplaza todos los datos en una transacción; requiere las migraciones ya aplicadas."""
    if not current_app.config.get("MODO_DEMO"):
        raise ErrorDeDominio("fuera_de_demo", "El reinicio solo está disponible en modo demo.", 403)
    reloj = reloj_actual()
    ahora = reloj.ahora()
    personas = generar_personas()
    contador = count(1)

    def siguiente_id():
        return id_ficticio(next(contador), ahora)

    socios = []
    with transaccion() as cursor:
        repositorio.vaciar_datos(cursor)
        sede_id = siguiente_id()
        repositorio.insertar_sede(cursor, sede_id, ahora, HORARIO_SEDE)
        for persona in personas:
            # La clave se descarta: nunca se imprime ni depende de random.Random(2026).
            usuario_id = permisos.crear_usuario(
                cursor,
                persona,
                persona["rol"],
                clave=secrets.token_urlsafe(32),
                es_demo=persona["es_demo"],
                identificadores=(siguiente_id(), siguiente_id()),
            )
            if persona["rol"] == "socio":
                socios.append(usuario_id)
            elif persona["rol"] == "recepcion":
                recepcion_id = usuario_id
            elif persona["rol"] == "entrenador":
                entrenador_id = usuario_id
        for socio_id in socios:
            repositorio.insertar_asignacion(cursor, siguiente_id(), socio_id, entrenador_id, ahora)
            # Un único intervalo ficticio por socio: treinta días inclusivos, sin superposiciones.
            desde = fecha_local(ahora) - (timedelta(days=30) if socio_id == socios[SOCIOS_ADICIONALES] else timedelta())
            repositorio.insertar_membresia(cursor, siguiente_id(), socio_id, desde, desde + timedelta(days=29), ahora)
        historial = generar_visitas(ahora, socios[SOCIOS_ADICIONALES + 1 :])
        repositorio.insertar_visitas(cursor, sede_id, recepcion_id, historial, siguiente_id)
        _cargar_programas(cursor, socios, siguiente_id, ahora)
        repositorio.insertar_restriccion(cursor, siguiente_id(), socios[1], entrenador_id, ahora)
        # El 80 % se redondea al entero más cercano.
        for socio_id in socios[: round(len(socios) * 0.8)]:
            permisos.registrar_consentimiento(
                cursor, socio_id, "salud", True, "demo-1", socio_id, identificador=siguiente_id()
            )
