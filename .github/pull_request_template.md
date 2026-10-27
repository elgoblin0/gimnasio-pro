Cierra #

## Qué cambia
<!-- 2 a 5 viñetas, en términos del glosario. -->

## Cómo se prueba
<!-- Pruebas nuevas o actualizadas, y qué fallaba antes del cambio. -->

## Rutas sensibles
- [ ] No toca `reglas/`, `migraciones/`, `comun/migrar.py`, `sincronizacion/`, `permisos/` ni `salud/`
- [ ] Toca rutas sensibles: necesita revisión de Opus

## Definición de terminado
- [ ] CI en verde (ruff, pytest, migraciones, secretos)
- [ ] `docs/capacidades.toml` y el mapa actualizados, si cambia una capacidad
- [ ] `INDICADORES.md` actualizado, si se movió código citado
- [ ] ADR provisional o `necesita-criterio`, si se decidió algo no cubierto

## Notas para el próximo agente
<!-- Qué quedó a medias, qué decidiste sin ADR, trampas encontradas, archivos clave. Breve. -->
