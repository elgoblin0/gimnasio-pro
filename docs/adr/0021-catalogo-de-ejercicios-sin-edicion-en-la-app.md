# 0021. Dejar el catálogo de ejercicios fuera de la edición en la app

- Estado: aceptado
- Fecha: 2026-10-30
- Decide: usuario
- Etiquetas: modulo:programas, modulo:entrenamiento

## Contexto
El ADR 0013 dejó para la etapa 4 la gestión del catálogo, de los equipos y de las alternativas por el entrenador. Las zonas del cuerpo y el patrón de movimiento de un ejercicio alimentan los frenos de seguridad: un error de carga en esos datos deja pasar un ejercicio contra un dolor reportado o una restricción de salud.

## Decisión
- Entrenador y administración editan solo las alternativas de cada ejercicio, con igual patrón de movimiento y distinto equipo, y el estado de los equipos.
- Los ejercicios, con sus zonas del cuerpo, patrón de movimiento, equipo e incremento de carga, siguen viniendo de la semilla. No hay alta ni edición en la app.

## Consecuencias
Los frenos parten siempre de datos revisados en el repositorio. Sumar un ejercicio requiere cambiar la semilla. La capacidad de equipos y alternativas de `VISION.md` queda cubierta, porque no promete editar el catálogo.

## Alternativas descartadas
- Alta y edición completas, como preveía el ADR 0013: abre una vía para debilitar los frenos sin aportar a la demo.
- Alta sin edición de zonas: un ejercicio nuevo igual necesita sus zonas para que los frenos actúen.
