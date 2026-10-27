-- =============================================
-- Migración 001: renombrar socios.dni -> socios.ci
-- Para quien ya tiene la base creada con la versión anterior.
-- Conserva todos los datos (no borra nada).
-- Se puede importar en phpMyAdmin (pestaña Importar) o correr con el cliente mysql.
-- Es segura de repetir: si la columna ya se llama "ci", no hace nada.
-- =============================================

USE gimnasio_pro;

SET @tiene_dni = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'gimnasio_pro' AND TABLE_NAME = 'socios' AND COLUMN_NAME = 'dni'
);

-- CHANGE COLUMN (en vez de RENAME COLUMN) para que ande también en MariaDB viejo
-- Conserva el UNIQUE, ya que es un índice sobre la columna.
SET @sql = IF(
    @tiene_dni = 1,
    'ALTER TABLE socios CHANGE COLUMN dni ci VARCHAR(20) NOT NULL',
    'SELECT ''Nada que migrar: socios.dni ya no existe'' AS resultado'
);

PREPARE migracion FROM @sql;
EXECUTE migracion;
DEALLOCATE PREPARE migracion;
