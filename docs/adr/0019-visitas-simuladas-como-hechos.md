# 0019. Registrar las visitas simuladas del modo demo como hechos, con tope del 80 % del aforo

- Estado: aceptado
- Fecha: 2026-10-29
- Decide: usuario
- Etiquetas: modulo:demo, modulo:visitas

## Contexto
La demo se reinicia a las 04:00 (ADR 0009) y nadie más entra, así que la escena de ocupación y el aforo en vivo mostrarían solo a quien esté probando. Render gratuito no tiene tareas en segundo plano y la app se duerme sin tráfico.

## Decisión
- En modo demo, la sede tiene socios ficticios marcados como simulados. Sus visitas simuladas son entradas y salidas comunes, con un usuario de sistema como autor (ADR 0003: solo `INSERT`).
- Las visitas simuladas se generan de forma determinista al llegar una consulta de ocupación, poniéndose al día desde el último instante generado hasta `reloj_actual()`; no hay temporizador.
- Pasan por la misma regla de entrada que las reales, y la simulación nunca deja la ocupación registrada por encima del 80 % del aforo máximo.
- La semilla trae además unas 8 semanas de visitas ficticias con un patrón creíble, para la permanencia habitual y los mejores horarios.
- Fuera del modo demo no se simula nada.

## Consecuencias
- Aforo, visitas por conciliar, permanencia habitual y mejores horarios usan un solo código, sin ramas para la demo.
- Quien prueba la demo siempre puede entrar: queda un 20 % del aforo libre de simulación.
- Las pantallas identifican las visitas simuladas; la tarjeta contextual de un socio simulado lo dice.
- Se verifica con pruebas de la simulación con reloj fijo (mismo instante, mismas visitas) y del tope.

## Alternativas descartadas
- Calcular las visitas simuladas al leer, sin guardarlas: obliga a mezclar datos en el aforo, la conciliación y los horarios, y la entrada atómica no las vería.
- Un temporizador que registre entradas: Render gratuito no lo sostiene y la app duerme sin tráfico.

<!-- Un ADR "provisional" lo tomó un agente sin el usuario; se revisa en el cierre de la etapa. -->
