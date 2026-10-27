# Visión de Gimnasio Pro

Fuente de verdad de la meta final. Si otro documento la contradice, manda este. Las decisiones que lo amplían se registran como ADR en `docs/adr/`.

## Meta

Gimnasio Pro es una demo y portfolio que muestra hasta dónde se llega con **Flask + JavaScript moderno + MySQL**, sin framework de frontend y sin paso de build. Gestiona el entrenamiento personalizado y la operación diaria de un gimnasio de una sola sede en Paraguay, con una experiencia visual de primer nivel (ver la dirección visual en `ROADMAP.md`).

Se considera terminada cuando una persona sin conocimientos técnicos recorre la demo pública en unos dos minutos, entiende qué hace el sistema y por qué, y cada capacidad del `docs/MAPA-CAPACIDADES.md` está al menos en nivel **pulida** con su prueba.

## Principios

1. **Sin IA en el producto.** Las propuestas y sus explicaciones salen de un motor de reglas determinista, versionado y probado. La explicación de una propuesta enumera las reglas que la produjeron.
2. **Ajustes automáticos con frenos.** La carga y el volumen se ajustan solos (doble progresión + RPE/RIR + chequeo del día). Los frenos de seguridad no se pueden desactivar.
3. **El historial no se reescribe.** Toda corrección agrega un registro con autor, fecha y motivo.
4. **Funciona sin conexión.** PWA: el socio registra su sesión aunque no haya red; al reconectar se sincroniza sin duplicar.
5. **Sin build.** Módulos ES, import maps y librerías copiadas al repo (Three.js, animación, gráficos).
6. **Datos ficticios y visibles como tales.** La demo nunca usa datos reales.
7. **Código y lenguaje en español**, según `GLOSSARY.md`.

## Capacidades incluidas

| Grupo | Capacidad |
|---|---|
| Entrenamiento | Sesión en vivo completa (series, descansos, carga anterior); "me duele" y "máquina ocupada" durante la sesión; chequeo del día; récords y progreso; doble progresión con RPE/RIR y ajustes automáticos con frenos |
| Programas | Programas armados por el entrenador desde plantillas; equipos y alternativas por ejercicio |
| Socio | Ficha completa con salud, restricciones y consentimientos; incorporación de 90 días y riesgo de abandono; resumen semanal |
| Recepción | Entrada y salida con tarjeta contextual del socio; aforo en vivo y mejores horarios; clases y reservas con lista de espera; registro de pagos en guaraníes |
| Entrenador | Bandeja priorizada de socios que requieren atención; revisión de ajustes frenados |
| Experiencia | Cuerpo 3D muscular; escena de ocupación; recorrido guiado; movimiento cuidado; versión móvil, accesible y con alternativa sin efectos |
| Acceso | Login real por rol y accesos rápidos "entrar como…" solo en modo demo |

## Fuera de alcance

- IA o modelos de lenguaje dentro del producto.
- QR rotativo para la entrada.
- Múltiples sedes (el modelo guarda la sede y su zona horaria, pero hay una sola).
- App nativa; la experiencia móvil es la PWA.
- Cobros en línea: los pagos se registran, no se procesan.

## Personas y recorridos

**Socio, en el celular.** Lucía abre la PWA al llegar. Responde el chequeo del día (sueño, energía, dolor). El sistema le propone la sesión y le explica por qué ("subís 2,5 kg en sentadilla: completaste 3×12 a RIR 2 la semana pasada"). Registra series con un toque; si una máquina está ocupada, recibe una alternativa equivalente; si algo le duele, lo marca y ese ejercicio se reemplaza o baja. Al terminar ve récords, progreso y el cuerpo 3D con los músculos trabajados.

**Recepción, en escritorio.** Rocío registra la entrada de un socio y ve su tarjeta contextual: membresía, pagos pendientes, avisos de salud relevantes para el personal, si está en sus primeros 90 días o en riesgo de abandono. Ve el aforo en vivo y la escena de ocupación, gestiona reservas de clases y registra pagos.

**Entrenador, en tablet.** Marcos abre su bandeja priorizada: ajustes frenados por dolor o restricción, socios nuevos sin programa, socios en riesgo de abandono. Arma programas desde plantillas, revisa las explicaciones del motor y corrige cuando hace falta.

**Administración, en escritorio.** Configura aforo, clases, plantillas, equipos y usuarios.

## Frenos de seguridad

Fijos, implementados en el motor de reglas y cubiertos por pruebas:

1. Nunca se sube la carga de un ejercicio con **dolor reportado** en la zona involucrada, ni en esa sesión ni en la siguiente.
2. Nunca se propone un ejercicio contra una **restricción de salud** registrada.
3. La suba de carga semanal por ejercicio tiene un **tope** (valor inicial en ADR provisional del motor).
4. Un chequeo del día malo puede bajar volumen o intensidad, nunca subirlos.
5. Cuando un freno actúa, el sistema **sustituye o baja** el ejercicio, lo explica al socio y **avisa al entrenador** en su bandeja.

## Demo pública

- Disponible desde temprano en un hosting gratuito con HTTPS (ver ADR 0009).
- Datos ficticios que se reinician solos cada día; un aviso visible lo indica.
- Accesos rápidos "entrar como socio / recepción / entrenador / administración".
- Límites de uso: tasa de solicitudes por IP, tamaño máximo de registros y operaciones destructivas acotadas.

## Paraguay como país de referencia

- Moneda: guaraníes, sin decimales, separador de miles con punto (₲ 250.000).
- Identificación: cédula de identidad (solo dígitos, se muestra con puntos: 4.567.890).
- Teléfonos: formato internacional +595; celulares +595 9XX XXX XXX.
- Fechas: dd/mm/aaaa; semana de lunes a domingo; zona horaria `America/Asuncion` (UTC−3 permanente desde 2024).
- Datos personales: Ley N.º 7593/2025 (ver ADR 0010). Salud es dato sensible: requiere consentimiento expreso y acceso restringido.

## Trazabilidad académica

`INDICADORES.md` debe seguir apuntando a archivos y líneas reales. Cada etapa que mueva código actualiza esas referencias.
