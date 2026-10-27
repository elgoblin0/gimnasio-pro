# Mapa de capacidades

Generado por `scripts/mapa_capacidades.py` desde `docs/capacidades.toml`. No editar a mano.

## Niveles

- **esqueleto**: Funciona de punta a punta con la semilla; lo prueba un e2e de humo.
- **funcional**: Cumple sus reglas y casos de aceptación; lo prueban pytest o node --test.
- **pulida**: Estados vacíos, carga y error, móvil, accesibilidad y movimiento; lo prueba un e2e con chequeo de accesibilidad.
- **validada**: El usuario la aprobó en un dispositivo real en el cierre de una etapa.

## Fundaciones

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Monolito modular con reglas de dependencia | 0 | funcional | `pruebas/test_dependencias.py::test_el_repo_cumple_las_reglas_de_dependencia` |
| Migraciones versionadas sobre MySQL | 0 | funcional | `pruebas/test_migrar.py::test_aplica_en_orden_y_la_segunda_pasada_no_hace_nada` |
| Reloj inyectable, UTC y zona de la sede | 0 | funcional | `pruebas/test_reloj.py::test_fecha_local_y_semana_al_cruzar_medianoche_en_asuncion` |
| Formatos de Paraguay (guaraníes, cédula, +595, fechas) | 0 | funcional | `pruebas/test_formatos.py::test_vectores_compartidos` |
| Idempotencia para escrituras | 1 | funcional | `pruebas/test_idempotencia.py::test_solicitudes_simultaneas_no_duplican` |

## Acceso

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Login real por rol | 0 | funcional | `pruebas/e2e/test_direccion_visual.py::test_ingreso_en_b_claro_y_oscuro_con_teclado_sin_desborde` |
| Accesos rápidos "entrar como…" en modo demo | 0 | funcional | `pruebas/e2e/test_direccion_visual.py::test_ingreso_en_b_claro_y_oscuro_con_teclado_sin_desborde` |

## Demo

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Semilla ficticia de Paraguay que se reinicia | 0 | funcional | `pruebas/test_demo_semilla.py::test_dos_reinicios_dejan_los_mismos_datos` |
| Demo pública en hosting gratuito con límites de uso | 1 | funcional | `pruebas/test_demo_limites.py` |

## Experiencia

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| PWA instalable en escritorio, con pantallas que se adaptan a tablet y celular | 1 | pendiente | — |
| Cuerpo 3D muscular | 2 | pendiente | — |
| Escena de ocupación | 3 | pendiente | — |
| Recorrido guiado de dos minutos | 7 | pendiente | — |
| Movimiento cuidado y alternativa sin efectos | 7 | pendiente | — |

## Entrenamiento

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Sesión en vivo completa | 2 | pendiente | — |
| Chequeo del día | 2 | pendiente | — |
| "Me duele" y "máquina ocupada" | 2 | pendiente | — |
| Doble progresión + RPE/RIR con ajustes automáticos y frenos | 2 | pendiente | — |
| Récords y progreso | 2 | pendiente | — |

## Recepción

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Tarjeta contextual en recepción | 3 | pendiente | — |
| Aforo en vivo y mejores horarios | 3 | pendiente | — |

## Entrenador

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Programas desde plantillas | 4 | pendiente | — |
| Bandeja priorizada del entrenador | 4 | pendiente | — |
| Equipos y alternativas | 4 | pendiente | — |

## Operación

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Clases y reservas con lista de espera | 5 | pendiente | — |
| Registro de pagos en guaraníes | 5 | pendiente | — |
| Ficha completa con salud y consentimientos | 5 | pendiente | — |

## Acompañamiento

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Incorporación de 90 días y riesgo de abandono | 6 | pendiente | — |
| Resumen semanal | 6 | pendiente | — |
