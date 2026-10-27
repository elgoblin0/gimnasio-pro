# Alcance funcional propuesto: entrenamiento y operación

Estado: diseño pendiente de implementación. Las funciones descritas aquí no existen todavía en la aplicación. La meta final está en [VISION.md](../VISION.md) y el avance real en [MAPA-CAPACIDADES.md](MAPA-CAPACIDADES.md). La ambición visual de Pro acompaña estas funciones; entrenamiento y operación son el núcleo del producto.

## Situación actual
Las rutinas actuales son descripciones elegidas por objetivo y nivel. Las asistencias solo guardan la entrada; no hay salida, sesiones realizadas, series ni aforo. La asignación actual y la regla de una entrada diaria deben revisarse al introducir visitas y reingresos.

## Entrenamiento personalizado
- Perfil con objetivo, experiencia, disponibilidad semanal, tiempo por sesión, preferencias y restricciones de ejercicios registradas por el entrenador.
- Catálogo estructurado de ejercicios: patrones de movimiento, grupos musculares, equipamiento, alternativas y medidas aplicables. Una serie de fuerza y un bloque de cardio no comparten obligatoriamente las mismas medidas.
- Programas versionados, armados por el entrenador desde plantillas. La progresión es doble progresión + RPE/RIR, ajustada por el chequeo del día.
- Ajustes de carga y volumen totalmente automáticos, con frenos fijos: nunca subir carga con dolor reportado ni contra una restricción de salud, y tope de suba semanal. Cuando un freno actúa, el sistema sustituye o baja el ejercicio y avisa al entrenador.
- Sesiones planificadas y realizadas independientes. Registrar ejercicios y series, repeticiones, carga, tiempo, distancia, esfuerzo percibido opcional y notas según corresponda.
- Registrar sesiones fuera del gimnasio y sesiones sin visita; una visita puede no contener entrenamiento. La presencia no prueba qué ejercicio se hizo.
- Balance semanal: comparar lo aprobado con lo realizado, incluidos entrenamientos parciales, sustituciones y cambios de programa.
- Proponer el próximo entrenamiento considerando secuencia pendiente, historial reciente, disponibilidad, tiempo disponible y restricciones del programa. Explicar las razones y permitir modificar la propuesta.
- Una ausencia no acumula automáticamente todo el trabajo en el día siguiente. Las reglas de recuperación y progresión son fijas y versionadas; el entrenador elige la plantilla y puede corregir. No inferir recuperación fisiológica solo por el tiempo transcurrido.
- Conservar el plan original y el historial de cambios. Completar una sesión tarde o corregir una serie recalcula el balance sin duplicar trabajo ni alterar silenciosamente el historial.

## Presencia y aforo
- Entrada identifica al socio, valida su membresía y abre una visita de manera atómica. Evitar duplicados por doble registro o reintentos de red (claves de idempotencia). No hay QR rotativo.
- Salida cierra la visita. Distinguir una salida confirmada, una corrección de recepción y un cierre estimado.
- Una sola visita abierta por socio como regla inicial; permitir otra visita tras la salida, sujeta a las condiciones de la membresía. El consumo del cupo de acceso requiere una regla explícita independiente del número de visitas.
- Una sola sede; igual se registran la sede y su zona horaria (`America/Asuncion`). Propuesta inicial: semana de entrenamiento de lunes a domingo en la zona de la sede; conservar separada la ventana móvil de siete días que hoy usa la membresía.
- Aforo máximo definido por el responsable; ocupación registrada calculada desde visitas abiertas. Si el límite aplica a todas las personas, incluir también personal e invitados.
- Verificar cupo y registrar entrada en una misma transacción para que dos entradas simultáneas no superen el límite. Configurar si alcanzar el aforo bloquea nuevas entradas o inicia una espera.
- Mostrar dentro/capacidad disponible, duración de cada visita e incidencias. Una salida olvidada genera una incidencia; nunca se convierte en salida confirmada por llegar a la duración habitual.
- Calcular permanencia habitual y rango orientativo con visitas confiables, mostrar cantidad de observaciones y estado de datos insuficientes. Excluir cierres estimados por defecto. Separar estimaciones de salidas y mediciones confirmadas.
- La presencia por zona exige registros específicos por zona; no se deduce de la rutina asignada. El estado de una máquina exige una fuente propia o confirmación del socio.

## Automatizaciones
1. Al registrar entrenamiento, recalcular trabajo pendiente y sugerencia siguiente.
2. Ante una ausencia, proponer reprogramación dentro de las reglas aprobadas.
3. Al entrar o salir, actualizar recepción y ocupación sin recargar la pantalla.
4. Ante una visita anormalmente larga, pedir conciliación a recepción.
5. Antes de una sesión, ofrecer alternativas compatibles si hay equipo fuera de servicio o una restricción aplicable.
6. Generar un resumen semanal para socio y entrenador: cumplimiento, cambios y pendientes.

Todo lo resuelve un motor de reglas determinista, versionado y comprobable, escrito como funciones puras. No hay IA en el producto: las explicaciones salen del propio motor, que enumera las reglas aplicadas. Los ajustes de carga son automáticos y respetan los frenos de seguridad de VISION.md.

## Ampliaciones incluidas
- Temporizador de descansos y recuperación de la última carga registrada.
- Reservas de clases con lista de espera y liberación de cupos.
- Asignación de entrenadores y bandeja de socios que requieren revisión.
- Equipos fuera de servicio y alternativas por equipamiento.
- Detección de registros duplicados y correcciones con autor, fecha y motivo.
- Horarios menos concurridos a partir del historial, diferenciando previsión y dato actual.
- Avisos configurables de sesiones y vencimientos.
- Chequeo del día, récords y progreso, cuerpo 3D muscular, escena de ocupación y recorrido guiado.
- Incorporación de 90 días, riesgo de abandono y resumen semanal.
- Permisos por rol: el socio ve sus registros; el entrenador solo los socios asignados; recepción gestiona accesos sin necesitar todo el historial personal.

## Primera entrega funcional
Recorrido completo con datos de demo: socio entra, se actualiza el aforo, recibe la sesión propuesta y su explicación, registra ejercicios y series, ve el balance semanal y registra su salida. Recepción ve presencia y duración; el entrenador puede corregir y reprogramar.

## Casos de aceptación imprescindibles
- Dos lecturas de entrada no abren dos visitas; dos entradas para el último cupo no superan el aforo.
- Una visita sin salida sigue identificada como pendiente de conciliación.
- Entrar y salir sin registrar ejercicio no completa entrenamiento.
- Una sesión parcial acredita solo lo registrado.
- Una ausencia no produce una sesión acumulada fuera de las reglas del programa.
- Una corrección conserva el historial y actualiza el balance.
- Los cálculos semanales y los accesos respetan sus ventanas temporales respectivas.

## Estructura técnica inicial
Monolito modular Flask con blueprints (ADR 0001) y frontend PWA sin build servido por la misma app (ADR 0007). Mantener inicialmente Flask y MySQL, incorporar migraciones versionadas y transacciones. Ejecutar los cambios de estado críticos en el backend y publicar sus actualizaciones después de confirmar la transacción. Añadir tareas programadas para resúmenes e incidencias y una vía de eventos para las pantallas activas. La escena 3D consume este mismo estado, con datos simulados identificados en el modo demo.
