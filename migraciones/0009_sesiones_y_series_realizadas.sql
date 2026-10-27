-- Hechos de entrenamiento en UTC; las correcciones agregan registros (ADR 0003).
CREATE TABLE IF NOT EXISTS sesiones_realizadas (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    sesion_planificada_id BINARY(16) NOT NULL,
    creada_en DATETIME(6) NOT NULL,
    KEY ix_realizadas_socio_fecha (socio_id, creada_en),
    KEY ix_realizadas_planificada (sesion_planificada_id),
    CONSTRAINT fk_realizadas_socio FOREIGN KEY (socio_id) REFERENCES usuarios (id),
    CONSTRAINT fk_realizadas_planificada FOREIGN KEY (sesion_planificada_id) REFERENCES sesiones_planificadas (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS series_realizadas (
    id BINARY(16) NOT NULL PRIMARY KEY,
    sesion_realizada_id BINARY(16) NOT NULL,
    ejercicio_planificado_id BINARY(16) NOT NULL,
    repeticiones INT NULL,
    carga DECIMAL(8,2) NULL,
    duracion INT NULL,
    distancia DECIMAL(10,2) NULL,
    autor_id BINARY(16) NOT NULL,
    registrada_en DATETIME(6) NOT NULL,
    corrige_a BINARY(16) NULL,
    motivo VARCHAR(500) NULL,
    anulada BOOLEAN NOT NULL DEFAULT FALSE,
    KEY ix_series_sesion_fecha (sesion_realizada_id, registrada_en),
    KEY ix_series_correccion (corrige_a),
    CONSTRAINT fk_series_sesion FOREIGN KEY (sesion_realizada_id) REFERENCES sesiones_realizadas (id),
    CONSTRAINT fk_series_ejercicio FOREIGN KEY (ejercicio_planificado_id) REFERENCES ejercicios_planificados (id),
    CONSTRAINT fk_series_autor FOREIGN KEY (autor_id) REFERENCES usuarios (id),
    CONSTRAINT fk_series_correccion FOREIGN KEY (corrige_a) REFERENCES series_realizadas (id),
    CONSTRAINT ck_series_repeticiones CHECK (repeticiones > 0),
    CONSTRAINT ck_series_carga CHECK (carga >= 0),
    CONSTRAINT ck_series_duracion CHECK (duracion > 0),
    CONSTRAINT ck_series_distancia CHECK (distancia > 0),
    CONSTRAINT ck_series_correccion CHECK (
        corrige_a IS NULL OR (corrige_a <> id AND motivo IS NOT NULL AND CHAR_LENGTH(TRIM(motivo)) > 0)
    ),
    CONSTRAINT ck_series_anulacion CHECK (anulada = FALSE OR corrige_a IS NOT NULL)
) ENGINE=InnoDB;
