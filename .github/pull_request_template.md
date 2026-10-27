Closes #
<!-- En inglés a propósito: GitHub solo cierra issues con sus palabras clave (Closes, Fixes, Resolves). -->

## Qué cambia
<!-- 2 a 5 viñetas, en términos del glosario. -->

## Cómo se prueba
<!-- Pruebas nuevas o actualizadas, y qué fallaba antes del cambio. -->

## Rutas sensibles
- [ ] No toca `reglas/`, `migraciones/`, `comun/migrar.py`, `permisos/` ni `salud/`
- [ ] Toca rutas sensibles: necesita la revisión de Codex y la de Opus sobre el diff

## Definición de terminado
- [ ] CI en verde (ruff, pytest, migraciones, secretos)
- [ ] `docs/capacidades/<id>.toml` y el mapa actualizados, si cambia una capacidad
- [ ] `INDICADORES.md` actualizado, si se movió código citado
- [ ] ADR provisional o `necesita-criterio`, si se decidió algo no cubierto

## Notas para el próximo agente
<!-- Qué quedó a medias, qué decidiste sin ADR, trampas encontradas, archivos clave. Breve. -->
