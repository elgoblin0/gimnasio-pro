# Mapa de capacidades

Generado por `scripts/mapa_capacidades.py` desde `docs/capacidades/`. No editar a mano.

## Niveles

- **esqueleto**: Funciona de punta a punta con la semilla; lo prueba un e2e de humo.
- **funcional**: Cumple sus reglas y casos de aceptación; lo prueban pytest o node --test.
- **pulida**: Estados vacíos, carga y error, móvil, accesibilidad y movimiento; lo prueba un e2e con chequeo de accesibilidad.
- **validada**: El usuario la aprobó en un dispositivo real en el cierre de una etapa.

## Acceso

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Accesos rápidos "entrar como…" en modo demo | 0 | funcional | `pruebas/e2e/test_direccion_visual.py::test_ingreso_en_b_claro_y_oscuro_con_teclado_sin_desborde` |
| Login real por rol | 0 | funcional | `pruebas/e2e/test_direccion_visual.py::test_ingreso_en_b_claro_y_oscuro_con_teclado_sin_desborde` |

## Fundaciones

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Monolito modular con reglas de dependencia | 0 | funcional | `pruebas/test_dependencias.py::test_el_repo_cumple_las_reglas_de_dependencia` |
| Formatos de Paraguay (guaraníes, cédula, +595, fechas) | 0 | funcional | `pruebas/test_formatos.py::test_vectores_compartidos` |
| Migraciones versionadas sobre MySQL | 0 | funcional | `pruebas/test_migrar.py::test_aplica_en_orden_y_la_segunda_pasada_no_hace_nada` |
| Reloj inyectable, UTC y zona de la sede | 0 | funcional | `pruebas/test_reloj.py::test_fecha_local_y_semana_al_cruzar_medianoche_en_asuncion` |
| Idempotencia para escrituras | 1 | funcional | `pruebas/test_idempotencia.py::test_solicitudes_simultaneas_no_duplican` |

## Demo

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Semilla ficticia de Paraguay con catálogo, recorrido e historial de visitas de ocho semanas | 0 | funcional | `pruebas/test_demo_semilla.py` |
| Demo pública en hosting gratuito con límites de uso | 1 | funcional | `pruebas/test_demo_limites.py` |

## Operación

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Entrada del socio por recepción con membresía y aforo | 1 | validada | `pruebas/e2e/test_esqueleto_andante.py` · https://github.com/elgoblin0/gimnasio-pro/issues/52 |
| Pantalla de recepción con sondeo de ocupación registrada y visitas abiertas, entrada, salida y conciliación | 1 | validada | `pruebas/e2e/test_recepcion.py` · https://github.com/elgoblin0/gimnasio-pro/issues/52 |
| Salida confirmada del socio y lecturas para recepción | 1 | validada | `pruebas/e2e/test_esqueleto_andante.py` · https://github.com/elgoblin0/gimnasio-pro/issues/52 |
| Clases y reservas con lista de espera | 5 | pendiente | — |
| Ficha completa con salud y consentimientos | 5 | pendiente | — |
| Registro de pagos en guaraníes | 5 | pendiente | — |

## Entrenamiento

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Persistencia de sesiones realizadas y series realizadas | 1 | funcional | `pruebas/test_entrenamiento_repositorio.py` |
| Pantalla del socio con propuesta, explicación, pendientes y ocupación registrada | 1 | validada | `pruebas/e2e/test_entrenamiento.py` · https://github.com/elgoblin0/gimnasio-pro/issues/52 |
| Registro idempotente de sesiones y series realizadas con RIR opcional y prescripción efectiva guardada | 1 | validada | `pruebas/e2e/test_esqueleto_andante.py` · https://github.com/elgoblin0/gimnasio-pro/issues/52 |
| Sesión propuesta según la secuencia, con rango de repeticiones y catálogo | 1 | validada | `pruebas/e2e/test_esqueleto_andante.py` · https://github.com/elgoblin0/gimnasio-pro/issues/52 |
| Chequeo del día | 2 | validada | `pruebas/e2e/test_recorrido_lucia.py::test_recorrido_lucia_etapa_2` · https://github.com/elgoblin0/gimnasio-pro/issues/136 |
| "Me duele" y "máquina ocupada" | 2 | validada | `pruebas/e2e/test_recorrido_lucia.py::test_recorrido_lucia_etapa_2` · https://github.com/elgoblin0/gimnasio-pro/issues/136 |
| Doble progresión + RPE/RIR con ajustes automáticos y frenos | 2 | validada | `pruebas/e2e/test_recorrido_lucia.py::test_recorrido_lucia_etapa_2` · https://github.com/elgoblin0/gimnasio-pro/issues/136 |
| Récords y progreso | 2 | validada | `pruebas/e2e/test_recorrido_lucia.py::test_recorrido_lucia_etapa_2` · https://github.com/elgoblin0/gimnasio-pro/issues/136 |
| Sesión en vivo completa | 2 | validada | `pruebas/e2e/test_recorrido_lucia.py::test_recorrido_lucia_etapa_2` · https://github.com/elgoblin0/gimnasio-pro/issues/136 |

## Infraestructura

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Verificación estática del historial que solo admite inserciones | 1 | funcional | `pruebas/test_historial_inserciones.py` |

## Recepción

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Historial de entradas y salidas con ocupación registrada | 1 | funcional | `pruebas/test_visitas.py` |
| Consulta de membresía de acceso por vigencia, sin cupo de entradas | 1 | funcional | `pruebas/test_socios_membresia.py` |
| Aforo en vivo y mejores horarios | 3 | funcional | `pruebas/test_mejores_horarios.py` |
| Tarjeta contextual en recepción | 3 | funcional | `pruebas/test_tarjeta_contextual.py` |

## Entrenador

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Lectura del programa de entrenamiento por socio y versión con catálogo y rango de repeticiones | 1 | funcional | `pruebas/test_programas.py` |
| Bandeja priorizada del entrenador | 4 | pendiente | — |
| Equipos y alternativas | 4 | pendiente | — |
| Programas desde plantillas | 4 | pendiente | — |

## Experiencia

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| PWA instalable en escritorio, con pantallas que se adaptan a tablet y celular | 1 | validada | `pruebas/e2e/test_pwa.py` · https://github.com/elgoblin0/gimnasio-pro/issues/52 |
| Cuerpo 3D muscular | 2 | validada | `pruebas/e2e/test_recorrido_lucia.py::test_recorrido_lucia_etapa_2` · https://github.com/elgoblin0/gimnasio-pro/issues/136 |
| Escena de ocupación | 3 | pendiente | — |
| Movimiento cuidado y alternativa sin efectos | 7 | pendiente | — |
| Recorrido guiado de dos minutos | 7 | pendiente | — |

## Acompañamiento

| Capacidad | Etapa | Nivel | Prueba |
|---|---|---|---|
| Incorporación de 90 días y riesgo de abandono | 6 | pendiente | — |
| Resumen semanal | 6 | pendiente | — |
