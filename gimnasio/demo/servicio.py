"""Recorrido ficticio reiniciable; identidades estables y credenciales opacas nuevas."""

import json
import random
import secrets
from collections import OrderedDict, deque
from datetime import UTC, date, datetime, time, timedelta
from itertools import count
from math import ceil
from threading import Lock
from typing import NamedTuple
from zoneinfo import ZoneInfo

from flask import current_app

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.formatos import normalizar_cedula, normalizar_telefono
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import ZONA_SEDE, fecha_local, reloj_actual
from gimnasio.comun.tipos import ZONAS_CUERPO
from gimnasio.demo import repositorio
from gimnasio.demo.nombres import APELLIDOS, NOMBRES
from gimnasio.permisos import servicio as permisos
from gimnasio.reglas.simulacion import simular_visitas
from gimnasio.reglas.version import VERSION_REGLAS
from gimnasio.salud.borrado import CEDULA_SOCIO_BORRADO_DEMO
from gimnasio.visitas import servicio as visitas

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
TIPOS_MEMBRESIA = (("Mensual", 30, 150_000), ("Trimestral", 90, 400_000), ("Anual", 365, 1_400_000))
# (nombre, día de la semana, hora, minutos, cupo): ocho clases semanales con Marcos.
CLASES = (
    ("Funcional", 1, time(7, 0), 60, 12),
    ("Funcional de la tarde", 1, time(19, 0), 60, 12),
    ("Yoga", 2, time(18, 30), 60, 15),
    ("Pilates", 3, time(9, 0), 50, 10),
    ("Spinning", 3, time(19, 0), 45, 12),
    ("Movilidad", 4, time(8, 0), 45, 15),
    ("Fuerza guiada", 5, time(18, 0), 60, 3),
    ("Cardio", 6, time(9, 0), 45, 12),
)
CLASE_LLENA, CLASE_CON_CUPO, CLASE_CANCELADA = "Fuerza guiada", "Yoga", "Spinning"
SOLICITUDES_POR_MINUTO = 240
VENTANA_DE_SOLICITUDES = timedelta(minutes=1)


class Actores(NamedTuple):
    recepcion: object
    entrenador: object
    administracion: object
    mensual: tuple
    id_pago: object  # Ids aparte: los de los pagos no desplazan a los de las identidades de los recorridos.


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
    _cargar_plantillas(cursor, siguiente_id, ahora, fuerza)
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
    return fuerza


def _cargar_plantillas(cursor, siguiente_id, ahora, fuerza):
    empuje, traccion = siguiente_id(), siguiente_id()
    for identificador, nombre, patron, zonas in (
        (empuje, "Press con mancuernas ficticio", "empuje horizontal", ("pecho", "hombros", "triceps")),
        (traccion, "Remo con mancuernas ficticio", "tracción horizontal", ("espalda_alta", "dorsales", "biceps")),
    ):
        repositorio.insertar_ejercicio(
            cursor,
            identificador,
            nombre,
            ["repeticiones", "carga"],
            ahora,
            patron_movimiento=patron,
            equipo="mancuernas",
            incremento_carga="2.50",
            zonas=zonas,
        )
    for nombre, dias in (("Inicial de cuerpo completo", 2), ("3 días", 3), ("4 días", 4)):
        plantilla = siguiente_id()
        repositorio.insertar_plantilla(cursor, plantilla, nombre, "Semana tipo ficticia de fuerza.", ahora)
        for posicion in range(1, dias + 1):
            sesion = siguiente_id()
            repositorio.insertar_sesion_plantilla(cursor, sesion, plantilla, posicion, f"Fuerza {posicion}")
            for orden, ejercicio in enumerate((fuerza, empuje, traccion), start=1):
                repositorio.insertar_ejercicio_plantilla(cursor, siguiente_id(), sesion, ejercicio, orden)


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
            "figura_cuerpo": "femenina" if nombre == "Lucía" and indice == 0 else None,
            "fecha_nacimiento": {0: date(1994, 3, 12), 4: date(1988, 9, 2)}.get(indice),
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

    contador_de_pagos = count(1 << 40)

    def id_pago():
        return id_ficticio(next(contador_de_pagos), ahora)

    socios = []
    with transaccion() as cursor:
        repositorio.vaciar_datos(cursor)
        sede_id = siguiente_id()
        repositorio.insertar_sede(cursor, sede_id, ahora, HORARIO_SEDE)
        tipos = [(id_pago(), nombre, dias, precio) for nombre, dias, precio in TIPOS_MEMBRESIA]
        repositorio.insertar_tipos_membresia(cursor, tipos, ahora)
        mensual = tipos[0]
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
            elif persona["rol"] == "administracion":
                administracion_id = usuario_id
        pagos, membresias = [], []
        for socio_id in socios:
            repositorio.insertar_asignacion(cursor, siguiente_id(), socio_id, entrenador_id, ahora)
            # Un único intervalo ficticio por socio: treinta días inclusivos, sin superposiciones.
            # El último socio adicional está vencido y el anterior vence en cuatro días.
            dias_atras = {socios[SOCIOS_ADICIONALES]: 30, socios[SOCIOS_ADICIONALES - 1]: 25}.get(socio_id, 0)
            desde = fecha_local(ahora) - timedelta(days=dias_atras)
            pago_id = id_pago()
            pagos.append(
                (
                    pago_id,
                    socio_id,
                    mensual[0],
                    "efectivo",
                    mensual[3],
                    recepcion_id,
                    ahora - timedelta(days=dias_atras),
                )
            )
            membresias.append((siguiente_id(), socio_id, desde, desde + timedelta(days=29), ahora, pago_id, mensual[0]))
        repositorio.insertar_pagos(cursor, pagos)
        repositorio.insertar_membresias_con_pago(cursor, membresias)
        historial = generar_visitas(ahora, socios[SOCIOS_ADICIONALES + 1 :])
        repositorio.insertar_visitas(cursor, sede_id, recepcion_id, historial, siguiente_id)
        ejercicio_fuerza = _cargar_programas(cursor, socios, siguiente_id, ahora)
        for nombre in repositorio.nombres_equipos_catalogo(cursor):
            repositorio.insertar_equipo(cursor, siguiente_id(), nombre, ahora)
        repositorio.insertar_restriccion(cursor, siguiente_id(), socios[1], entrenador_id, ahora)
        # Los socios de los recorridos conservan los frenos de salud.
        for socio_id in socios:
            permisos.registrar_consentimiento(
                cursor, socio_id, "salud", True, "demo-1", socio_id, identificador=siguiente_id()
            )

        _cargar_simulacion(cursor, siguiente_id, ahora)
        actores = Actores(recepcion_id, entrenador_id, administracion_id, mensual, id_pago)
        _cargar_bandeja(cursor, siguiente_id, entrenador_id, ahora, actores)
        _cargar_operacion(cursor, siguiente_id, ahora, socios, actores, ejercicio_fuerza)


def _cargar_simulacion(cursor, siguiente_id, ahora):
    for indice in range(61):
        persona = {
            "nombre": "Simulación" if indice == 60 else NOMBRES[indice % len(NOMBRES)],
            "apellido": "demo" if indice == 60 else APELLIDOS[indice % len(APELLIDOS)],
            "cedula": str(97_000_001 + indice),
            "telefono": f"+595970{indice:06d}",
            "correo": "simulacion@demo.gimnasio.invalid" if indice == 60 else f"simulada{indice}@demo.gimnasio.invalid",
        }
        usuario_id = permisos.crear_usuario(
            cursor,
            persona,
            "recepcion" if indice == 60 else "socio",
            identificadores=(siguiente_id(), siguiente_id()),
        )
        if indice < 60:
            repositorio.marcar_simulada(cursor, usuario_id)
            desde = fecha_local(ahora)
            repositorio.insertar_membresia(cursor, siguiente_id(), usuario_id, desde, desde + timedelta(days=29), ahora)
    repositorio.iniciar_simulacion(cursor, ahora)


def poner_al_dia():
    """Agrega visitas en una transacción serializada, exclusivamente en la demo."""
    if not current_app.config.get("MODO_DEMO"):
        return
    with transaccion() as cursor:
        # Mismo orden que recepción: sede y luego simulación, incluso con idempotencia.
        sede, abiertas = visitas.estado_para_simulacion(cursor)
        if sede is None:
            return
        estado = repositorio.bloquear_simulacion(cursor)
        if estado is None:
            return
        ahora = reloj_actual().ahora()
        desde = estado["generada_hasta"].replace(tzinfo=UTC)
        if desde >= ahora:
            return
        zona = ZoneInfo(sede["zona_horaria"])
        desde = max(desde, ahora - timedelta(hours=24)).astimezone(zona)
        hasta = ahora.astimezone(zona)
        horario = json.loads(sede["horario"]) if isinstance(sede["horario"], (str, bytes)) else sede["horario"]
        simulados = [desde_bytes(fila["id"]) for fila in repositorio.listar_simulados(cursor)]
        autor = desde_bytes(repositorio.obtener_autor_simulacion(cursor)["id"])
        presentes = {
            desde_bytes(fila["socio_id"]): fila["registrada_en"].replace(tzinfo=UTC).astimezone(zona)
            for fila in abiertas
            if fila["simulada"]
        }
        entradas = {
            desde_bytes(fila["socio_id"]): desde_bytes(fila["entrada_id"]) for fila in abiertas if fila["simulada"]
        }
        ocupacion_real = sum(not fila["simulada"] for fila in abiertas)
        while desde < hasta:
            fin = min(hasta, datetime.combine(desde.date() + timedelta(days=1), time(), zona))
            eventos = simular_visitas(
                desde,
                fin,
                horario,
                sede["aforo_maximo"],
                simulados,
                presentes,
                ocupacion_real,
                int(desde.strftime("%Y%m%d")),
            )
            for tipo, socio, instante in eventos:
                if tipo == "entrada":
                    entrada_id = nuevo_id()
                    visitas.registrar_entrada_en_transaccion(
                        cursor,
                        {"id": entrada_id, "socio_id": socio, "sede_id": desde_bytes(sede["id"])},
                        {"id": str(autor)},
                        instante.astimezone(UTC),
                    )
                    entradas[socio] = entrada_id
                    presentes[socio] = instante
                else:
                    visitas.registrar_salida_en_transaccion(
                        cursor, entradas.pop(socio), autor, instante.astimezone(UTC)
                    )
                    presentes.pop(socio)
            desde = fin
        repositorio.avanzar_simulacion(cursor, ahora)


def _cargar_bandeja(cursor, siguiente_id, entrenador_id, ahora, actores):
    """Casos independientes del recorrido y agregados después de sus identidades estables."""
    ejercicio, con_alternativa, sin_alternativa = (siguiente_id() for _ in range(3))
    for identificador, nombre, equipo in (
        (ejercicio, "Remo sin equipo ficticio", "sin equipo"),
        (con_alternativa, "Remo en polea ficticio", "polea"),
        (sin_alternativa, "Remo en máquina ficticio", "máquina de remo"),
    ):
        repositorio.insertar_ejercicio(
            cursor,
            identificador,
            nombre,
            ["repeticiones", "carga"],
            ahora,
            patron_movimiento="tracción horizontal",
            equipo=equipo,
            incremento_carga="2.50",
            zonas=("espalda_alta", "dorsales", "biceps"),
        )
    repositorio.insertar_alternativa(cursor, con_alternativa, ejercicio, 1)
    for nombre in ("polea", "máquina de remo"):
        equipo = siguiente_id()
        repositorio.insertar_equipo(cursor, equipo, nombre, ahora)
        repositorio.insertar_equipo_fuera_de_servicio(cursor, siguiente_id(), equipo, entrenador_id, ahora)

    for indice in range(1, 9):
        socio = permisos.crear_usuario(
            cursor,
            {
                "nombre": NOMBRES[indice],
                "apellido": APELLIDOS[indice],
                "cedula": str(96_000_000 + indice),
                "telefono": f"+595960{indice:06d}",
                "correo": f"bandeja{indice}@demo.gimnasio.invalid",
            },
            "socio",
            identificadores=(siguiente_id(), siguiente_id()),
        )
        repositorio.insertar_asignacion(cursor, siguiente_id(), socio, entrenador_id, ahora)
        _membresia_con_pago(cursor, siguiente_id, ahora, socio, actores)
        permisos.registrar_consentimiento(cursor, socio, "salud", True, "demo-1", socio, identificador=siguiente_id())
        if indice == 3:
            continue  # Socio sin programa.
        programa, sesion, planificado = siguiente_id(), siguiente_id(), siguiente_id()
        repositorio.insertar_programa(cursor, programa, socio, ahora)
        repositorio.insertar_sesion_planificada(cursor, sesion, programa, 1, "Fuerza ficticia")
        catalogo = sin_alternativa if indice == 5 else con_alternativa if indice == 8 else ejercicio
        repositorio.insertar_ejercicio_planificado(
            cursor,
            planificado,
            sesion,
            catalogo,
            1,
            2,
            repeticiones_minimas=8,
            repeticiones_maximas=12,
            rir_objetivo=2,
            descanso=90,
            carga="20.50",
        )
        if indice == 4:
            repositorio.insertar_historial(
                cursor,
                siguiente_id(),
                (siguiente_id(), siguiente_id()),
                socio,
                sesion,
                planificado,
                ahora,
                12,
            )
        freno = {1: "dolor_reportado", 2: "restriccion_salud", 6: "chequeo_desfavorable", 7: "dolor_reportado"}.get(
            indice
        )
        if freno:
            aviso = siguiente_id()
            repositorio.insertar_aviso(
                cursor,
                aviso,
                siguiente_id(),
                socio,
                sesion,
                entrenador_id,
                freno,
                [{"regla": freno, "version": VERSION_REGLAS, "datos": {"ejercicio_id": str(catalogo)}}],
                ahora,
            )
            if indice == 7:
                repositorio.insertar_revision_aviso(cursor, siguiente_id(), aviso, entrenador_id, ahora)


def _proxima_ocurrencia(ahora, dia_semana, hora):
    """Primera fecha, desde hoy, en que la clase todavía no empezó: la agenda siempre tiene una vigente."""
    local = ahora.astimezone(ZONA_SEDE).replace(tzinfo=None)
    dia = local.date()
    for _ in range(8):
        if dia.isoweekday() == dia_semana and datetime.combine(dia, hora) > local:
            return dia
        dia += timedelta(days=1)


def _membresia_con_pago(cursor, siguiente_id, ahora, socio, actores):
    pago, tipo = actores.id_pago(), actores.mensual
    repositorio.insertar_pagos(cursor, [(pago, socio, tipo[0], "efectivo", tipo[3], actores.recepcion, ahora)])
    desde = fecha_local(ahora)
    repositorio.insertar_membresias_con_pago(
        cursor, [(siguiente_id(), socio, desde, desde + timedelta(days=29), ahora, pago, tipo[0])]
    )


def _alta_socio(cursor, siguiente_id, ahora, actores, cedula, nombre, apellido, *, entrenador=True, es_demo=False):
    """Socio ficticio con membresía mensual pagada y consentimiento de salud propio, como los de la semilla."""
    socio = permisos.crear_usuario(
        cursor,
        {
            "nombre": nombre,
            "apellido": apellido,
            "cedula": cedula,
            "telefono": f"+595950{int(cedula) % 1_000_000:06d}",
            "correo": f"operacion{cedula}@demo.gimnasio.invalid",
            "fecha_nacimiento": date(1985 + int(cedula) % 15, 1 + int(cedula) % 12, 1 + int(cedula) % 28),
        },
        "socio",
        clave=secrets.token_urlsafe(32) if es_demo else None,
        es_demo=es_demo,
        identificadores=(siguiente_id(), siguiente_id()),
    )
    _membresia_con_pago(cursor, siguiente_id, ahora, socio, actores)
    if entrenador:
        repositorio.insertar_asignacion(cursor, siguiente_id(), socio, actores.entrenador, ahora)
    permisos.registrar_consentimiento(cursor, socio, "salud", True, "demo-1", socio, identificador=siguiente_id())
    return socio


def _programa_con_historial(cursor, siguiente_id, socio, ejercicio, ahora):
    programa, sesion, planificado = siguiente_id(), siguiente_id(), siguiente_id()
    repositorio.insertar_programa(cursor, programa, socio, ahora)
    repositorio.insertar_sesion_planificada(cursor, sesion, programa, 1, "Fuerza ficticia")
    repositorio.insertar_ejercicio_planificado(
        cursor,
        planificado,
        sesion,
        ejercicio,
        1,
        2,
        repeticiones_minimas=8,
        repeticiones_maximas=12,
        rir_objetivo=2,
        descanso=90,
        carga="20.50",
    )
    repositorio.insertar_historial(
        cursor, siguiente_id(), (siguiente_id(), siguiente_id()), socio, sesion, planificado, ahora, 12
    )


def _cargar_clases(cursor, siguiente_id, ahora, socios, hugo, actores):
    """Ocho clases semanales; la llena (con Hugo primero en espera), la de cupo libre y la cancelada ya fijadas."""
    clases = {nombre: (siguiente_id(), dia, hora, minutos, cupo) for nombre, dia, hora, minutos, cupo in CLASES}
    repositorio.insertar_clases(
        cursor,
        [(i, nombre, dia, hora, minutos, cupo) for nombre, (i, dia, hora, minutos, cupo) in clases.items()],
        actores.entrenador,
        ahora,
    )
    ocurrencias = {}
    for nombre in (CLASE_LLENA, CLASE_CON_CUPO, CLASE_CANCELADA):
        clase, dia, hora, minutos, _ = clases[nombre]
        ocurrencias[nombre] = siguiente_id()
        repositorio.insertar_ocurrencia(
            cursor, ocurrencias[nombre], clase, _proxima_ocurrencia(ahora, dia, hora), hora, minutos, ahora
        )
    pedidas = (
        # Cupo 3: Lucía y otros dos socios tienen lugar; Hugo es el primero de la espera.
        (CLASE_LLENA, (socios[0], socios[2], socios[3], hugo, socios[4])),
        (CLASE_CON_CUPO, (socios[6], socios[7])),
        (CLASE_CANCELADA, (socios[5],)),
    )
    base = ahora - timedelta(hours=3)
    repositorio.insertar_reservas(
        cursor,
        [
            (siguiente_id(), ocurrencias[nombre], socio, base + timedelta(minutes=10 * posicion))
            for nombre, pedidos in pedidas
            for posicion, socio in enumerate(pedidos)
        ],
    )
    repositorio.insertar_cancelacion_ocurrencia(
        cursor,
        siguiente_id(),
        ocurrencias[CLASE_CANCELADA],
        "Mantenimiento de la sala de spinning (ficticio).",
        actores.administracion,
        ahora,
    )
    repositorio.insertar_aviso_socio(
        cursor, siguiente_id(), socios[5], ocurrencias[CLASE_CANCELADA], "ocurrencia_cancelada", ahora
    )


def _cargar_operacion(cursor, siguiente_id, ahora, socios, actores, ejercicio):
    """Casos de la etapa 5, agregados al final para no mover las identidades de los recorridos anteriores."""
    hugo = _alta_socio(cursor, siguiente_id, ahora, actores, "95000001", "Hugo", "Rolón", es_demo=True)
    dedicado = _alta_socio(
        cursor, siguiente_id, ahora, actores, CEDULA_SOCIO_BORRADO_DEMO, "Dalila", "Borrado", es_demo=True
    )
    revocado = _alta_socio(cursor, siguiente_id, ahora, actores, "95000002", "Rafael", "Revocado")
    _alta_socio(cursor, siguiente_id, ahora, actores, "95000003", "Silvia", "Sola", entrenador=False)
    permisos.registrar_consentimiento(
        cursor, revocado, "salud", False, "demo-1", revocado, identificador=siguiente_id()
    )
    _programa_con_historial(cursor, siguiente_id, revocado, ejercicio, ahora)
    _cargar_clases(cursor, siguiente_id, ahora, socios, hugo, actores)

    perfiles = (
        (socios[0], "Ganar fuerza", "intermedia", 3, 60, "Prefiere entrenar por la mañana."),
        (socios[1], "Mejorar la resistencia", "inicial", 4, 45, "Sin preferencias."),
        (hugo, "Bajar de peso", "inicial", 3, 45, "Prefiere las clases grupales."),
        (dedicado, "Mantenerse activa", "intermedia", 2, 60, "Entrena los fines de semana."),
        (revocado, "Ganar masa muscular", "avanzada", 5, 90, "Prefiere las mancuernas."),
    )
    for socio, objetivo, experiencia, disponibilidad, tiempo, preferencias in perfiles:
        repositorio.insertar_perfil(
            cursor,
            socio,
            {
                "objetivo": objetivo,
                "experiencia": experiencia,
                "disponibilidad_semanal": disponibilidad,
                "tiempo_por_sesion": tiempo,
                "preferencias": preferencias,
            },
            actores.administracion,
            ahora,
        )

    # Salud: una condición sin revisar en la bandeja de Marcos y un aviso para el personal en una tarjeta.
    repositorio.insertar_condicion(
        cursor,
        siguiente_id(),
        hugo,
        "Hernia discal leve, sin dolor al caminar (ficticio).",
        ahora,
    )
    repositorio.insertar_aviso_personal(
        cursor,
        siguiente_id(),
        socios[SOCIOS_ADICIONALES - 1],
        "Prefiere que le avisen por mensaje y no por llamada (ficticio).",
        actores.administracion,
        ahora,
    )
    # El socio dedicado al borrado tiene datos de salud y una condición ya revisada. Sin programa: cada programa
    # suma consultas a la bandeja de Marcos y el presupuesto de la demo ya está al límite.
    condicion = siguiente_id()
    repositorio.insertar_condicion(
        cursor, condicion, dedicado, "Asma leve controlada con inhalador (ficticio).", ahora - timedelta(days=2)
    )
    repositorio.insertar_revision_condicion(
        cursor, siguiente_id(), condicion, actores.entrenador, ahora - timedelta(days=1)
    )
    repositorio.insertar_restriccion(cursor, siguiente_id(), dedicado, actores.entrenador, ahora)
    repositorio.insertar_aviso_personal(
        cursor,
        siguiente_id(),
        dedicado,
        "Avisar antes de subir la intensidad (ficticio).",
        actores.administracion,
        ahora,
    )
    repositorio.insertar_consultas_ficha(
        cursor,
        [
            (siguiente_id(), socios[0], actores.entrenador, ahora - timedelta(days=dias, hours=horas))
            for dias, horas in ((3, 1), (2, 4), (1, 2))
        ],
    )
