# 0026. Tratar el perfil de entrenamiento como dato personal fuera de la ficha de salud

- Estado: provisional
- Fecha: 2026-10-31
- Decide: Opus
- Etiquetas: modulo:socios, modulo:entrenador, migraciones/, permisos/

## Contexto
El issue #221 crea `perfiles_entrenamiento` con objetivo, experiencia, disponibilidad semanal, tiempo por sesión y preferencias, pero el término no estaba en el glosario (duda de Codex en el PR #237). Falta decidir si es dato de salud (ADR 0006, 0010, 0024 y 0025), quién lo ve y si se guarda como hecho (ADR 0003).

## Decisión
- El **perfil de entrenamiento** es un dato personal no sensible. No requiere el consentimiento de salud, no genera una consulta de ficha y la revocación de salud no lo oculta ni lo borra.
- Lo ven y editan solo el socio y su entrenador asignado vigente. Recepción y administración no lo reciben. Si el socio cambia de entrenador, el perfil se conserva y lo ve el nuevo entrenador.
- El formulario declara su finalidad (ADR 0010) y pide no escribir datos de salud: esos van en la ficha de salud, como condición de salud.
- Es un estado actualizable, no un hecho: una fila por socio que se sobrescribe, con `actualizado_en` y `actualizado_por`. No guarda versiones anteriores.
- El motor de reglas no lo lee. Usarlo en las reglas necesita un ADR nuevo.

## Consecuencias
El perfil sale en la etapa 5 sin el peso de los controles de salud. Si un socio escribe datos de salud en «preferencias», quedan fuera de esos controles: la finalidad del formulario lo desalienta, pero no lo impide. Una prueba verifica que cambiar el perfil no altera la propuesta y otra, que recepción no lo recibe.

## Alternativas descartadas
- Guardarlo dentro de la ficha de salud: exigiría consentimiento para datos que no son sensibles y lo ocultaría al revocar.
- Guardarlo como hechos con historial: nadie lo necesita todavía y complica la consulta.
