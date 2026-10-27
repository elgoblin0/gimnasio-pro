# Versión Pro

## Objetivo
Explorar el techo del producto mediante una experiencia completa para socios, recepción, entrenadores y administradores. Elegir tecnologías mantenidas y versiones estables vigentes al implementar cada etapa; el stack definitivo todavía está pendiente.

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
