# 0032. Hacer el recorrido guiado sobre la app real de la demo compartida

- Estado: aceptado
- Fecha: 2026-11-02
- Decide: usuario
- Etiquetas: modulo:demo

## Contexto
El recorrido guiado (etapa 7) muestra el producto en unos dos minutos: un socio entra y recepción ve el aforo, el socio cuenta que durmió mal y registra su sesión, el entrenador revisa el freno y el socio termina con su resumen, sus récords y su cuerpo iluminado. La demo pública es una sola instancia compartida: varios visitantes pueden entrar a la vez como el mismo socio de la semilla, que se reinicia una vez por día.

## Decisión
- El recorrido guiado navega las pantallas reales y ejecuta acciones reales (entrada, series, salida) con los socios de la semilla, sin pantallas ni datos de mentira.
- Cada paso lee el estado que encuentra y se adapta: si otro visitante ya hizo la acción, el paso lo dice y sigue («Lucía ya está adentro»). Ningún paso falla por el estado que dejó otro visitante.
- Las escrituras usan `Idempotency-Key` como cualquier POST (ADR 0004); los hechos solo se insertan (ADR 0003).
- El visitante puede salir en cualquier paso y queda en la app real, en la pantalla de ese paso. Terminar el recorrido desde el último paso, en cambio, cierra la sesión y vuelve a la portada para entrar con cualquier rol.
- El recorrido cierra con el resumen de la sesión que el socio acaba de registrar, no con una pantalla de administración: es el momento de impacto. Registra una repetición más que la vez anterior, para que el récord que se ve sea uno que el recorrido batió de verdad.
- Antes de una acción que importa, el paso la anuncia y deja verla: la pantalla ya muestra lo que el socio contó, unos segundos antes de guardarlo. Si el visitante sale mientras tanto, la acción no ocurre.
- La tarjeta va siempre al pie de la vista y la pantalla lleva la parte explicada al espacio libre: no se corta ni tapa el comienzo de lo que explica en ningún tamaño.
- Enmienda del 2026-11-02 tras un recorrido crítico de la demo: pasa de 10 a 7 pasos y deja afuera la pantalla de administración.

## Consecuencias
- Lo que se ve es el producto: lo que funciona en el recorrido funciona fuera de él.
- Dos recorridos simultáneos pueden ver el trabajo del otro. Se acepta en la demo.
- Un paso no puede suponer un estado inicial: el e2e del recorrido lo corre dos veces seguidas sobre la misma semilla y ambas terminan.

## Alternativas descartadas
- Solo narrar y dejar las escrituras a la simulación: se pierde el «lo hice yo», que es el momento de impacto.
- Crear un socio ficticio por recorrido: ensucia la base con personas sin historia y exige armar programa e historial en cada visita.
