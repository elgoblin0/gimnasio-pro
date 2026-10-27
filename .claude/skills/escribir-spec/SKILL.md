---
name: escribir-spec
description: Convertir la conversación actual en la spec de una etapa o función de Gimnasio Pro y publicarla como issue de GitHub, sin volver a interrogar. Usar después de interrogar, o cuando el dueño pide la spec.
---

Sintetizá lo que ya se habló; no interrogues.

1. Si todavía no exploraste, leé lo que toca la spec: `GLOSSARY.md`, los ADR del área, `VISION.md`, la sección de la etapa en `ROADMAP.md` y el código vigente. Usá los términos del glosario y respetá los ADR.
2. Bosquejá las **costuras de prueba**: dónde se va a probar el comportamiento. Preferí las que ya existen y la más alta posible; lo ideal es una sola. Confirmalas con el dueño.
3. Escribí la spec con esta plantilla y publicala.

## Plantilla

```md
## Problema
El problema desde la perspectiva del socio, el entrenador o la recepción.

## Solución
La solución desde esa misma perspectiva.

## Historias de usuario
Lista numerada LARGA que cubra todos los aspectos:
1. Como <actor>, quiero <función>, para <beneficio>.

## Decisiones de implementación
Módulos que se crean o cambian y sus interfaces, decisiones de arquitectura, cambios de esquema, contratos de API, interacciones puntuales y los ADR que aplican. Sin rutas de archivo ni código: envejecen rápido. Excepción: un fragmento de un prototipo que fija una decisión mejor que la prosa (máquina de estados, esquema), recortado a lo esencial y marcado como tal.

## Decisiones de prueba
Qué hace buena a una prueba (comportamiento externo, no detalles internos), qué módulos se prueban y qué pruebas existentes sirven de modelo.

## Fuera de alcance

## Notas
```

## Publicar

```bash
gh issue create --title "Spec: <etapa o función>" --label tipo:docs --label ejecutor:opus --milestone "Etapa N: …" --body-file - <<'EOF'
…
EOF
```

Sin `estado:listo`: la spec no se implementa, la implementan sus tickets. Terminado: el issue existe y le pasaste el número al dueño.
