CREATE TABLE clases (
    id BINARY(16) PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    entrenador_id BINARY(16) NOT NULL,
    dia_semana TINYINT UNSIGNED NOT NULL,
    hora_inicio TIME NOT NULL,
    duracion_minutos SMALLINT UNSIGNED NOT NULL,
    cupo INT NOT NULL,
    archivada BOOLEAN NOT NULL DEFAULT FALSE,
    creada_en DATETIME(6) NOT NULL,
    actualizada_en DATETIME(6) NOT NULL,
    FOREIGN KEY (entrenador_id) REFERENCES usuarios(id),
    CHECK (dia_semana BETWEEN 1 AND 7),
    CHECK (duracion_minutos BETWEEN 15 AND 240),
    CHECK (cupo > 0)
);

CREATE TABLE ocurrencias_clase (
    id BINARY(16) PRIMARY KEY,
    clase_id BINARY(16) NOT NULL,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    duracion_minutos SMALLINT UNSIGNED NOT NULL,
    creada_en DATETIME(6) NOT NULL,
    UNIQUE (clase_id, fecha),
    FOREIGN KEY (clase_id) REFERENCES clases(id),
    CHECK (duracion_minutos BETWEEN 15 AND 240),
    INDEX (fecha)
);
