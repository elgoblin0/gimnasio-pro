-- Chequeo del día y aviso genérico por freno (#88): hechos de solo inserción.
CREATE TABLE IF NOT EXISTS chequeos_dia (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    fecha_local DATE NOT NULL,
    sueno TINYINT NOT NULL,
    energia TINYINT NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    KEY ix_chequeo_ultimo (socio_id, fecha_local, registrado_en, id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    CHECK (sueno BETWEEN 1 AND 5),
    CHECK (energia BETWEEN 1 AND 5)
);
CREATE TABLE IF NOT EXISTS avisos_entrenador (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    entrenador_id BINARY(16) NULL,
    sesion_realizada_id BINARY(16) NOT NULL,
    freno VARCHAR(64) NOT NULL,
    explicacion JSON NOT NULL,
    creado_en DATETIME(6) NOT NULL,
    UNIQUE KEY uq_aviso_freno (sesion_realizada_id, freno),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (entrenador_id) REFERENCES usuarios(id),
    FOREIGN KEY (sesion_realizada_id) REFERENCES sesiones_realizadas(id)
);
