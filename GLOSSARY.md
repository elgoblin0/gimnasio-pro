# Gimnasio Pro

Lenguaje del entrenamiento personalizado y la operación del gimnasio.

## Entrenamiento

**Programa de entrenamiento**:
Plan individual de varias semanas que reúne objetivos, sesiones y criterios de progresión.
_Evitar_: Plan, cuando pueda confundirse con una membresía.

**Sesión planificada**:
Entrenamiento previsto con ejercicios, objetivos de trabajo y una fecha o posición dentro de una secuencia.
_Evitar_: Asistencia, visita.

**Sesión realizada**:
Entrenamiento registrado por el socio o el entrenador, completo o parcial, con lo que efectivamente se hizo.
_Evitar_: Rutina completada por el solo hecho de ingresar al gimnasio.

**Serie realizada**:
Ejecución registrada de una serie de un ejercicio, con sus medidas aplicables: repeticiones, carga, duración o distancia.

**Ejercicio hecho**:
Ejercicio del catálogo que el socio realmente ejecutó en una serie realizada. Si no se registró otro, es el del ejercicio planificado.

**Pendiente de entrenamiento**:
Trabajo planificado todavía no realizado, que puede requerir reprogramación, sustitución o revisión.
_Evitar_: Deuda de ejercicio.

## Operación

**Membresía**:
Derecho de acceso del socio con vigencia y condiciones de uso.
_Evitar_: Programa de entrenamiento, plan sin calificar.

**Tipo de membresía**:
Oferta del gimnasio con nombre, duración y precio en guaraníes, configurada por administración.
_Evitar_: Plan, cuota.

**Pago pendiente**:
Situación de un socio cuya membresía venció o vence en 7 días o menos sin una renovación pagada.
_Evitar_: Deuda.

**Visita**:
Permanencia del socio en una sede, desde su entrada hasta su salida.
_Evitar_: Sesión de entrenamiento.

**Ocupación registrada**:
Cantidad de personas cuya presencia está registrada como abierta en una sede.
_Evitar_: Ocupación real cuando faltan registros de entrada o salida.

**Aforo máximo**:
Límite de personas permitido para una sede o zona, configurado por su responsable.

**Permanencia habitual**:
Estimación de cuánto suele durar una visita, obtenida de visitas con entrada y salida confiables.
_Evitar_: Hora de salida confirmada.

**Sede**:
Lugar físico del gimnasio, con su zona horaria. Gimnasio Pro maneja una sola sede.

**Entrada / Salida**:
Registros que abren y cierran una visita. Una salida puede ser confirmada, corregida por recepción o estimada.

**Visita por conciliar**:
Visita abierta que ya dura anormalmente más que la permanencia habitual. Recepción la cierra con una salida corregida y su motivo; nunca se cierra sola.
_Evitar_: Visita vencida, incidencia sin calificar.

**Zona de la sede**:
Área física de la sede (por ejemplo, musculación o cardio) donde se ubican sus equipos. La escena de ocupación ubica a las personas en estas zonas.
_Evitar_: Zona, sin calificar (choca con **Zona del cuerpo**); sector, área.

**Tarjeta contextual**:
Resumen del socio que ve recepción al registrar su entrada: membresía, pagos pendientes, avisos para el personal, incorporación y riesgo de abandono. No muestra el detalle de salud.

**Mejores horarios**:
Franjas con menor ocupación prevista, calculadas desde el historial de visitas. Es una previsión, no un dato actual.

**Escena de ocupación**:
Visualización interactiva de la ocupación registrada de la sede, con las personas ubicadas por zona de la sede y las visitas simuladas identificadas como tales en el modo demo.

## Progresión y seguridad

**Carga**:
Peso o resistencia de una serie, en kilogramos.
_Evitar_: Carga de trabajo (usar **Volumen**).

**Volumen**:
Cantidad de trabajo de un ejercicio o sesión: series por repeticiones, o tiempo y distancia cuando corresponda.

**Doble progresión**:
Regla que primero sube repeticiones dentro de un rango y, al completar el tope del rango en todas las series, sube la carga y vuelve al piso del rango.

**RPE**:
Esfuerzo percibido de una serie, de 1 a 10.

**RIR**:
Repeticiones que el socio cree que le quedaban en reserva al terminar una serie. RIR 2 equivale a RPE 8.

**Chequeo del día**:
Respuestas breves del socio antes de entrenar (sueño, energía, dolor) que pueden bajar el volumen o la intensidad de la sesión, nunca subirlos.

**Ajuste automático**:
Cambio de carga o volumen que el motor de reglas aplica sin intervención del entrenador, siempre dentro de los frenos.

**Freno de seguridad**:
Regla fija que impide un ajuste automático: dolor reportado, restricción de salud, tope de suba semanal o chequeo del día desfavorable. Cuando actúa, el sistema sustituye o baja el ejercicio y avisa al entrenador.
_Evitar_: Bloqueo, alerta.

**Dolor reportado**:
Aviso del socio, durante la sesión o en el chequeo del día, de dolor en una zona del cuerpo. Activa un freno sobre los ejercicios que la involucran.

**Restricción de salud**:
Condición registrada en la ficha que excluye ejercicios, patrones de movimiento o zonas.

**Sustitución**:
Reemplazo de un ejercicio planificado por una alternativa equivalente, por freno, máquina ocupada o equipo fuera de servicio.

**Máquina ocupada**:
Aviso del socio de que el equipo de un ejercicio no está disponible en ese momento. Produce una sustitución, no un cambio en el programa.

**Equipo**:
Tipo de máquina o implemento del gimnasio (por ejemplo, prensa), con su estado (disponible o fuera de servicio). No distingue unidades físicas.

**Alternativa**:
Ejercicio que puede reemplazar a otro porque comparte patrón de movimiento con equipamiento distinto. Por máquina ocupada tiene las mismas zonas del cuerpo; por dolor reportado involucra solo zonas del original, sin las zonas con dolor (ADR 0017).

**Zona del cuerpo**:
Región muscular o articular de una lista fija, común al dolor reportado, las restricciones de salud, los ejercicios y el cuerpo 3D.
_Evitar_: Grupo muscular, parte del cuerpo.

**Figura del cuerpo**:
Forma con que se muestra el cuerpo 3D: masculina o femenina. La elige cada persona y solo cambia la imagen, no las zonas del cuerpo ni las reglas de entrenamiento (ADR 0020).

**Incremento de carga**:
Paso fijo en que sube o baja la carga de un ejercicio, según su equipamiento. El tope de suba semanal es un incremento por ejercicio.

**Aviso al entrenador**:
Registro que deja un freno de seguridad al actuar, con el socio, el freno y su explicación, para que el entrenador lo revise.
_Evitar_: Alerta, notificación.

**Aviso revisado**:
Aviso al entrenador sobre el que el entrenador dejó constancia de haberlo visto, con una nota opcional. No deshace lo que hizo el freno.
_Evitar_: Ajuste frenado, aviso resuelto.

**Explicación**:
Lista de las reglas del motor que produjeron una propuesta o un ajuste, con los datos que usaron.

**Récord personal**:
Mejor marca registrada de un socio en un ejercicio para una medida (carga, repeticiones a una carga, distancia o tiempo).

## Programas y acompañamiento

**Plantilla de programa**:
Programa genérico que el entrenador usa como base para armar el programa de entrenamiento de un socio.

**Semana tipo**:
Conjunto de sesiones que el entrenador arma para una semana y que se repite durante toda la duración del programa de entrenamiento.

**Secuencia terminada**:
Estado de un programa de entrenamiento sin trabajo planificado pendiente. El socio no recibe propuesta hasta que el entrenador publica una versión nueva.
_Evitar_: Programa vencido, programa completado.

**Carga de partida**:
Carga que el entrenador fija para un ejercicio en una versión del programa. Vale hasta la primera serie registrada de ese ejercicio en esa versión; con historial, solo puede dejar la carga igual o más baja que la del motor.

**Bandeja del entrenador**:
Lista priorizada de socios asignados que requieren atención: condiciones de salud sin revisar, avisos sin revisar, socios sin programa, secuencia terminada, ejercicios sin alternativa disponible, socios sin consentimiento de salud y riesgo de abandono.

**Perfil de entrenamiento**:
Lo que el socio cuenta para orientar su programa de entrenamiento: objetivo, experiencia (inicial, intermedia o avanzada), disponibilidad semanal, tiempo por sesión y preferencias. Lo editan el socio y su entrenador asignado; el motor de reglas no lo usa. No es parte de la ficha de salud (ADR 0026).
_Evitar_: Perfil sin calificar, cuestionario.

**Incorporación**:
Primeros 90 días de un socio desde su alta, con seguimiento específico.

**Hito de incorporación**:
Paso que se calcula solo durante la incorporación: programa asignado, primera visita y primera sesión realizada.

**Riesgo de abandono**:
Indicador calculado por reglas (asistencia, tendencia y señales) de que un socio puede dejar de venir. No es una predicción estadística, no usa datos de salud y lo ve el personal, no el socio.

**Resumen semanal**:
Informe para socio y entrenador con lo cumplido, los cambios y los pendientes de la semana (lunes a domingo).

**Clase**:
Actividad grupal con horario semanal, entrenador y cupo. Se reserva en cada una de sus ocurrencias. No cuenta como sesión realizada ni afecta el aforo.

**Ocurrencia de clase**:
Una clase en una fecha concreta. Se puede cancelar sin cambiar el horario de la clase. Una vez empezada conserva el cupo que tenía, aunque cambie el de la clase.
_Evitar_: Turno, sesión.

**Reserva**:
Lugar de un socio en una ocurrencia de clase.

**Lista de espera**:
Orden de llegada de los socios sin cupo en una ocurrencia de clase. Al liberarse un cupo antes del inicio, el primero pasa solo a tener reserva.

**Aviso al socio**:
Registro que le informa al socio un cambio en sus reservas: pasó a tener lugar, volvió a la lista de espera o se canceló la ocurrencia. Queda en su inicio hasta que lo marca como visto.
_Evitar_: Notificación.

**Aviso para el personal**:
Frase corta que el entrenador asignado escribe para recepción, sin detalle de salud. Se muestra en la tarjeta contextual solo con consentimiento de salud vigente.
_Evitar_: Aviso de salud, aviso sin calificar.

**Pago registrado**:
Constancia de un pago en guaraníes hecho fuera del sistema, que renueva la membresía del socio. Gimnasio Pro no procesa cobros.

**Anulación de pago**:
Registro con autor y motivo que deja sin efecto un pago registrado, sin borrarlo.

## Personas y datos

**Rol**:
Función de un usuario: socio, recepción, entrenador o administración. Define qué puede ver y hacer.

**Consentimiento**:
Autorización expresa, versionada y revocable del socio para un tratamiento de datos, en especial los de salud.

**Revocación de salud**:
Retiro reversible del consentimiento de salud: detiene el tratamiento, sin borrar los datos.
_Evitar_: Borrado.

**Borrado de datos de salud**:
Anonimización irreversible de los datos de salud de un socio, que él pide con el consentimiento ya revocado (ADR 0025).
_Evitar_: Revocación.

**Datos personales**:
Nombre, apellido, cédula, teléfono, correo y fecha de nacimiento del socio. Recepción y administración los corrigen; el socio edita solo su teléfono y su correo.

**Ficha del socio**:
Datos personales del socio y, cuando la ven él mismo o su entrenador asignado, su perfil de entrenamiento. Nunca incluye la ficha de salud. Para el socio, la pantalla se llama «Mi ficha».
_Evitar_: Ficha sin calificar, cuando pueda confundirse con la ficha de salud.

**Ficha de salud**:
Datos sensibles del socio: condiciones, restricciones y dolores. Solo la ven el socio y su entrenador asignado.

**Condición de salud**:
Lo que el socio declara sobre su salud en texto libre. No activa frenos hasta que el entrenador asignado la traduce en una restricción de salud.
_Evitar_: Restricción, cuando todavía no la registró el entrenador.

**Consulta de ficha**:
Registro de cada lectura de la ficha de salud por parte del personal, con quién y cuándo. El socio la puede ver.
_Evitar_: Acceso, log.

**Cédula**:
Cédula de identidad paraguaya. Se guarda solo con dígitos y se muestra con puntos.

## Producto y demo

**Modo demo**:
Configuración de la instancia pública: datos ficticios que se reinician solos, accesos rápidos "entrar como…" y límites de uso.

**Cuerpo 3D muscular**:
Modelo 3D que resalta las zonas del cuerpo trabajadas o con dolor reportado.

**Visita simulada**:
Visita de un socio ficticio que el modo demo registra sola para que la sede tenga movimiento. Cuenta para la ocupación registrada como cualquier otra y se identifica como simulada.
_Evitar_: Visita falsa, visita de prueba.

**Recorrido guiado**:
Demostración paso a paso de unos dos minutos que muestra el producto a alguien sin conocimientos técnicos.

**Movimiento cuidado**:
Animaciones que explican cambios de estado, fluidas a 60 fps y desactivables con la preferencia de movimiento reducido.
