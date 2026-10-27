# 0008. Versionar las migraciones de MySQL con un aplicador propio

- Estado: aceptado
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
El esquema crecerá en cada etapa y la demo pública se reinicia sola. El proyecto no usa ORM: escribe SQL parametrizado con `mysql-connector-python`. En MySQL el DDL hace commit implícito, así que una migración no se puede revertir dentro de una transacción.

## Decisión
- Archivos `migraciones/NNNN_descripcion.sql` con cuatro dígitos, solo hacia adelante y sin "down".
- El aplicador, `python -m gimnasio.comun.migrar`:
  - registra cada migración en `migraciones_aplicadas(version, nombre, sha256, aplicada_en)`;
  - aplica en orden las pendientes, sentencia por sentencia;
  - se detiene si cambió la suma de una migración ya aplicada.
- Cada migración hace un solo cambio lógico y usa `IF NOT EXISTS` donde MySQL lo permite.
- El archivo heredado `migraciones/001_dni_a_ci.sql`, de tres dígitos, queda fuera del aplicador: pertenece al esquema heredado de `base_datos.sql`.
- El CI aplica todas las migraciones sobre una base vacía de MySQL 8.4 y verifica que una segunda pasada no haga nada.
- Ruta sensible: Opus revisa `migraciones/` y el aplicador.

## Consecuencias
El aplicador son unas 100 líneas propias, sin dependencias y con SQL legible para la rúbrica. Si una migración falla a mitad de camino, se corrige con una migración nueva.

## Alternativas descartadas
- Alembic: requiere SQLAlchemy, que el proyecto no usa.
- yoyo-migrations: requiere otro driver de MySQL (PyMySQL o mysqlclient), y su rollback no sirve con el DDL de MySQL.
