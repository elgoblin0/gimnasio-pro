# 0028. Mostrar al entrenador de la clase la lista de reservas de sus ocurrencias

- Estado: aceptado el 2026-11-01 por el dueño en el cierre de etapa 5 (#235)
- Fecha: 2026-10-31
- Decide: Opus
- Etiquetas: modulo:clases, permisos/

## Contexto
El ADR 0006 limita al entrenador a sus socios asignados. La clase tiene un entrenador (`clases.entrenador_id`) y cualquier socio con membresía vigente puede reservarla, esté asignado a ese entrenador o no. Para dar la clase, el entrenador necesita saber quiénes vienen (#218). Con la regla del ADR 0006 tal cual, vería una lista incompleta.

## Decisión
- El entrenador de una clase ve la lista de reservas de las ocurrencias de **esa** clase: los socios con reserva y los de la lista de espera, con su posición. Es una excepción acotada al alcance del ADR 0006 y no lo amplía para nada más.
- La lista tiene por persona solo el nombre (el de su persona, como en las demás listas), el estado de su reserva (con lugar o en espera) y la posición en la espera. No lleva cédula, contacto, membresía, pagos, perfil de entrenamiento, tarjeta contextual ni ficha de salud, y no enlaza a la ficha del socio.
- La excepción no hace del socio un socio asignado: no habilita `socios.ver_asignados`, `salud.ver_asignados` ni `entrenamiento.ver_asignados` sobre él, ni lo agrega a la bandeja del entrenador.
- Permiso `clases.ver_reservas` para `recepcion`, `administracion` y `entrenador`. Para el entrenador, el servicio comprueba que la clase sea suya: si no lo es, responde 403, igual que con un socio no asignado.
- Se decide con el entrenador **actual** de la clase. Si la clase cambia de entrenador, el anterior deja de ver sus listas, también las de ocurrencias pasadas.

## Consecuencias
El entrenador puede preparar su clase sin ver más datos de los necesarios (minimización, ADR 0010). La matriz suma una celda por rol para `clases.ver_reservas` y una prueba de que un entrenador no ve la lista de la clase de otro. La respuesta de la lista no incluye campos fuera de los nombrados; una prueba lo verifica.

## Alternativas descartadas
- Mostrarle solo sus socios asignados dentro de la lista: no sirve para dar la clase.
- Asignarle cada socio que reserva: mezcla una actividad grupal con el seguimiento personal y le abriría la ficha de salud.
- Que la lista la vea solo recepción y administración: deja al entrenador sin saber quién viene.
