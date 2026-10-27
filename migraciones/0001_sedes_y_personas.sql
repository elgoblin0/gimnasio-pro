-- Sede única (con su zona horaria) y personas. Ids UUIDv7 en BINARY(16) (ADR 0004); fechas en UTC (ADR 0005).
CREATE TABLE IF NOT EXISTS sedes (
    id BINARY(16) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    zona_horaria VARCHAR(64) NOT NULL DEFAULT 'America/Asuncion',
    aforo_maximo SMALLINT UNSIGNED NOT NULL,
    actualizada_en DATETIME(6) NOT NULL
);

CREATE TABLE IF NOT EXISTS personas (
    id BINARY(16) NOT NULL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL,
    apellido VARCHAR(80) NOT NULL,
    cedula VARCHAR(8) NOT NULL,
    telefono VARCHAR(16) NULL,
    correo VARCHAR(160) NULL,
    fecha_nacimiento DATE NULL,
    creada_en DATETIME(6) NOT NULL,
    actualizada_en DATETIME(6) NOT NULL,
    UNIQUE KEY uq_personas_cedula (cedula),
    UNIQUE KEY uq_personas_correo (correo),
    CONSTRAINT ck_personas_cedula CHECK (cedula REGEXP '^[0-9]{5,8}$')
);
