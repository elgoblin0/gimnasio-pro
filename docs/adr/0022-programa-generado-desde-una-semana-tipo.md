# 0022. Generar el programa completo desde una semana tipo

- Estado: aceptado
- Fecha: 2026-10-30
- Decide: usuario
- Etiquetas: modulo:programas

## Contexto
El motor propone la primera sesión planificada con pendientes, y una serie realizada acredita para siempre: la secuencia no se reinicia. Un programa con solo las sesiones de una semana dejaría al socio sin propuesta después de esa semana. El entrenador, en cambio, piensa en una semana que se repite.

## Decisión
- El entrenador arma una semana tipo y elige la duración, de 4 a 12 semanas, con 8 por defecto.
- Al publicar, se generan todas las sesiones planificadas en una sola secuencia, con nombres como «Semana 2 · Fuerza».
- La secuencia sigue el orden de lo realizado, no el calendario: quien falta una semana no pierde sesiones y termina más tarde.
- Al terminar la secuencia, el socio no recibe propuesta hasta que el entrenador publica una versión nueva.
- Límites: de 1 a 6 sesiones por semana, de 1 a 12 ejercicios por sesión y hasta 10 series por ejercicio.

## Consecuencias
La selección de sesión del motor no cambia y sigue sin acumular trabajo por una ausencia. Un programa puede llegar a 72 sesiones planificadas. Publicar una versión nueva reinicia la secuencia, y lo ya realizado sigue contando para la progresión.

## Alternativas descartadas
- Que el motor recicle la semana: cambia reglas ya aceptadas y obliga a reinterpretar qué acredita cada serie, sin ganar nada visible.
- Atar cada sesión a una fecha: una ausencia dejaría sesiones vencidas y contradice la regla de no acumular.
