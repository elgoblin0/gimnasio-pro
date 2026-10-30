# Versión Pro

## Objetivo
Explorar el techo del producto mediante una experiencia completa para socios, recepción, entrenadores y administradores. La meta final y sus límites están en [VISION.md](VISION.md). Stack: Flask, MySQL y JavaScript moderno sin framework ni build (ver `docs/adr/`).

El núcleo funcional es administrar entrenamiento personalizado y la operación real del gimnasio: programas, sesiones diarias, ejercicios y series realizados, balance semanal, propuestas automáticas explicables, entradas, salidas, permanencia y aforo. Ver [alcance funcional propuesto](docs/ALCANCE-FUNCIONAL.md) y [glosario](GLOSSARY.md). La experiencia visual debe representar estos procesos y sus datos.

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
- [x] Prototipar las direcciones visuales de la etapa 0; se conserva Cuaderno de entrenamiento (B).
- [x] Fijar B en los tokens de diseño y retirar A, por decisión del usuario en #33.
- [ ] Construir la primera escena interactiva con la dirección elegida (etapa 2).
- [ ] Verificar apariencia, fluidez, accesibilidad y adaptación antes de extender el diseño.

## Preparación completada
- [x] Conservar el historial original y la etiqueta `base-original`.
- [x] Crear un repositorio independiente de la versión estándar.
- [x] Separar la base de datos (`gimnasio_pro`) y el puerto local (5002).

## Etapas
Cada etapa es un milestone de GitHub y termina con un issue "Cierre de etapa N", la demo pública actualizada y el mapa de capacidades al día. El usuario interviene solo en ese cierre.

0. **Fundaciones:** visión, ADR de base, protocolo de agentes, CI, despachador, estructura de módulos, reloj, autenticación mínima, semilla con formatos de Paraguay, tokens de diseño, primer e2e y dirección visual B elegida.
1. **Esqueleto andante:** un recorrido de punta a punta en la demo pública: entrar, sesión propuesta, registrar series, salir. PWA instalable en escritorio y pantallas adaptadas a celular.
2. **Socio + cuerpo 3D:** sesión en vivo completa, chequeo del día, "me duele" / "máquina ocupada", doble progresión con RPE/RIR y frenos, récords y progreso, cuerpo 3D muscular.
3. **Recepción + escena de ocupación:** tarjeta contextual, aforo en vivo, mejores horarios, escena de ocupación.
4. **Entrenador:** programas desde plantillas, bandeja priorizada, revisión de ajustes frenados, equipos y alternativas.
5. **Operación:** clases y reservas con lista de espera, registro de pagos en guaraníes, ficha completa con salud y consentimientos, gestión de plantillas y configuración de aforo y usuarios por administración.
6. **Acompañamiento:** incorporación de 90 días, riesgo de abandono, resumen semanal.
7. **Pulido y recorrido guiado:** recorrido guiado de dos minutos, movimiento cuidado en todo el producto, rendimiento, accesibilidad y alternativa sin efectos.

Quedan fuera: IA en el producto, QR rotativo, múltiples sedes y app nativa.

## Primera demostración objetivo
Un socio entra, recepción y aforo se actualizan, el sistema propone su sesión según el programa y lo realizado esta semana, el socio registra ejercicios y series, consulta qué queda pendiente y registra su salida. El entrenador puede revisar y ajustar la propuesta. Después se amplía a reservas y pagos. El sistema ajusta carga y volumen solo, dentro de los frenos de seguridad, y avisa al entrenador cuando un freno actúa.

## Relación con la estándar
Origen: https://github.com/elgoblin0/gimnasio, etiqueta `base-original`. Conservar el remoto `upstream` como referencia. Revisar correcciones y trasladar solo las aplicables; no asumir compatibilidad futura entre esquemas de datos.
