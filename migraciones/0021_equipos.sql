-- Estado de los equipos mediante un historial que solo agrega (#176).
CREATE TABLE IF NOT EXISTS equipos (
    id BINARY(16) NOT NULL PRIMARY KEY,
    nombre VARCHAR(64) NOT NULL UNIQUE,
    creado_en DATETIME(6) NOT NULL,
    CHECK (nombre NOT IN ('', 'sin equipo'))
);

CREATE TABLE IF NOT EXISTS cambios_estado_equipo (
    id BINARY(16) NOT NULL PRIMARY KEY,
    equipo_id BINARY(16) NOT NULL,
    estado VARCHAR(32) NOT NULL,
    motivo VARCHAR(500) NULL,
    autor_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    KEY ix_cambios_equipo (equipo_id, registrado_en, id),
    FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id),
    CHECK (estado IN ('disponible', 'fuera_de_servicio'))
);
