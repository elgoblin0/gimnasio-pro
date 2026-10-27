# Versión Pro

## Objetivo
Explorar el techo del producto mediante una experiencia completa para socios, recepción, entrenadores y administradores. Elegir tecnologías mantenidas y versiones estables vigentes al implementar cada etapa; el stack definitivo todavía está pendiente.

La ambición visual es **cutting edge**: ser una demo de lo más avanzado que se pueda imaginar y construir con la tecnología disponible, con un impacto «wow» inmediato para cualquier persona que la vea. Esta es una meta central del producto y debe orientar las decisiones de interfaz, interacción y presentación.

## Dirección visual y criterios de aceptación
- **Primera impresión memorable:** una pantalla inicial con composición, tipografía, iluminación y profundidad propias; la identidad debe reconocerse también dentro de la aplicación.
- **Movimiento de alta calidad:** transiciones entre vistas, microinteracciones y respuestas a gestos coordinadas. El movimiento debe explicar los cambios de estado y sentirse fluido.
- **Escenas inmersivas:** explorar 3D interactivo, materiales, shaders y efectos de luz cuando eleven la experiencia del gimnasio. Validar estas ideas en prototipos antes de incorporarlas.
- **Datos que se puedan explorar:** indicadores y visualizaciones con transiciones, filtros y respuestas claras; diseñar una escena memorable de ocupación, actividad o progreso.
- **Una demo que cualquiera pueda disfrutar:** recorrido guiado con datos de ejemplo y momentos de impacto comprensibles sin saber programación ni gestión de gimnasios.
- **Calidad en todo el recorrido:** formularios, estados vacíos, carga, errores, confirmaciones y versión móvil deben tener el mismo cuidado que la portada.
- **Fluidez verificable:** apuntar a 60 fps en las interacciones principales del dispositivo de referencia; medir tiempos de carga y rendimiento antes de aceptar efectos costosos.
- **Accesibilidad y adaptación:** navegación con teclado, contraste legible, preferencia de movimiento reducido y alternativa funcional para equipos sin los efectos gráficos avanzados.
- **Tecnología vigente:** investigar las opciones actuales al iniciar la implementación, comparar prototipos y documentar la selección. No declarar un stack como «lo último» sin verificarlo.

La aceptación visual requiere revisar el resultado en navegador, escritorio y celular: impacto de los primeros segundos, coherencia del sistema visual y una demostración completa de aproximadamente dos minutos. El efecto «wow» se valida mostrando el prototipo a personas con distintos perfiles y recogiendo sus impresiones.

## Próxima entrega: prototipo visual
- [ ] Definir identidad y explorar dos direcciones visuales de alta ambición.
- [ ] Elegir una dirección y construir una primera escena interactiva que establezca el techo visual.
- [ ] Prototipar el recorrido de demo con datos ficticios, identificados como tales.
- [ ] Verificar apariencia, fluidez, accesibilidad y adaptación antes de extender el diseño al producto completo.

Esta entrega visual precede a la ampliación funcional para fijar el nivel de calidad desde el comienzo. Las escenas y tecnologías mencionadas son exploraciones pendientes.

## Preparación completada
- [x] Conservar el historial original y la etiqueta `base-original`.
- [x] Crear un repositorio independiente de la versión estándar.
- [x] Separar la base de datos (`gimnasio_pro`) y el puerto local (5002).

## Etapas propuestas
1. **Base confiable:** validaciones, transacciones, configuración por entorno, autenticación y permisos por rol, pruebas de flujos críticos y CI.
2. **Experiencia de producto:** diseño adaptable, panel de recepción, portal del socio, accesibilidad y datos de demostración.
3. **Operación completa:** clases, cupos, reservas, lista de espera, membresías, registro de pagos y check-in por QR.
4. **Gestión avanzada:** múltiples sedes, notificaciones, auditoría e indicadores de ocupación, ingresos y renovaciones.
5. **IA e integraciones:** asistente con acceso controlado a los datos y aprobación del entrenador para propuestas de rutinas; evaluar proveedores, costos y utilidad antes de integrar.
6. **Entrega operable:** despliegue automatizado, monitoreo, copias de seguridad y restauración comprobada.

Cada etapa debe terminar con una demostración funcional y criterios de aceptación. Estas capacidades son propuestas pendientes, no funciones disponibles.

## Primera demostración objetivo
Un socio reserva una clase, recepción registra su entrada y el administrador consulta la ocupación. Después se amplía a pagos, múltiples sedes e IA.

## Relación con la estándar
Origen: https://github.com/elgoblin0/gimnasio, etiqueta `base-original`. Conservar el remoto `upstream` como referencia. Revisar correcciones y trasladar solo las aplicables; no asumir compatibilidad futura entre esquemas de datos.
