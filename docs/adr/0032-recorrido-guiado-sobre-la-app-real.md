# 0032. Hacer el recorrido guiado sobre la app real de la demo compartida

- Estado: aceptado
- Fecha: 2026-11-02
- Decide: usuario
- Etiquetas: modulo:demo

## Contexto
El recorrido guiado (etapa 7) muestra el producto en unos dos minutos: un socio entra, recepción ve el aforo, el socio registra su sesión, el entrenador revisa un freno y la administración ve el resumen. La demo pública es una sola instancia compartida: varios visitantes pueden entrar a la vez como el mismo socio de la semilla, que se reinicia una vez por día.

## Decisión
- El recorrido guiado navega las pantallas reales y ejecuta acciones reales (entrada, series, salida) con los socios de la semilla, sin pantallas ni datos de mentira.
- Cada paso lee el estado que encuentra y se adapta: si otro visitante ya hizo la acción, el paso lo dice y sigue («Lucía ya está adentro»). Ningún paso falla por el estado que dejó otro visitante.
- Las escrituras usan `Idempotency-Key` como cualquier POST (ADR 0004); los hechos solo se insertan (ADR 0003).
- El visitante puede salir en cualquier paso y queda en la app real, en la pantalla de ese paso.

## Consecuencias
- Lo que se ve es el producto: lo que funciona en el recorrido funciona fuera de él.
- Dos recorridos simultáneos pueden ver el trabajo del otro. Se acepta en la demo.
- Un paso no puede suponer un estado inicial: el e2e del recorrido lo corre dos veces seguidas sobre la misma semilla y ambas terminan.

## Alternativas descartadas
- Solo narrar y dejar las escrituras a la simulación: se pierde el «lo hice yo», que es el momento de impacto.
- Crear un socio ficticio por recorrido: ensucia la base con personas sin historia y exige armar programa e historial en cada visita.
