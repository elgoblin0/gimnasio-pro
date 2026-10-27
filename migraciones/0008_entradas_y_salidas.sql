-- Visitas: entradas y salidas confirmadas. Las correcciones solo agregan hechos (ADR 0003).
CREATE TABLE IF NOT EXISTS entradas (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    sede_id BINARY(16) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrada_en DATETIME(6) NOT NULL,
    corrige_a BINARY(16) NULL,
    motivo VARCHAR(500) NULL,
    anulada BOOLEAN NOT NULL DEFAULT FALSE,
    KEY ix_entradas_socio_fecha (socio_id, registrada_en),
    KEY ix_entradas_sede_fecha (sede_id, registrada_en),
    CONSTRAINT fk_entradas_socio FOREIGN KEY (socio_id) REFERENCES usuarios (id),
    CONSTRAINT fk_entradas_sede FOREIGN KEY (sede_id) REFERENCES sedes (id),
    CONSTRAINT fk_entradas_autor FOREIGN KEY (autor_id) REFERENCES usuarios (id),
    CONSTRAINT fk_entradas_correccion FOREIGN KEY (corrige_a) REFERENCES entradas (id),
    CONSTRAINT ck_entradas_correccion CHECK (
        corrige_a IS NULL OR (corrige_a <> id AND motivo IS NOT NULL AND CHAR_LENGTH(TRIM(motivo)) > 0)
    ),
    CONSTRAINT ck_entradas_anulacion CHECK (anulada = FALSE OR corrige_a IS NOT NULL)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS salidas (
    id BINARY(16) NOT NULL PRIMARY KEY,
    entrada_id BINARY(16) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrada_en DATETIME(6) NOT NULL,
    corrige_a BINARY(16) NULL,
    motivo VARCHAR(500) NULL,
    anulada BOOLEAN NOT NULL DEFAULT FALSE,
    KEY ix_salidas_entrada_fecha (entrada_id, registrada_en),
    CONSTRAINT fk_salidas_entrada FOREIGN KEY (entrada_id) REFERENCES entradas (id),
    CONSTRAINT fk_salidas_autor FOREIGN KEY (autor_id) REFERENCES usuarios (id),
    CONSTRAINT fk_salidas_correccion FOREIGN KEY (corrige_a) REFERENCES salidas (id),
    CONSTRAINT ck_salidas_correccion CHECK (
        corrige_a IS NULL OR (corrige_a <> id AND motivo IS NOT NULL AND CHAR_LENGTH(TRIM(motivo)) > 0)
    ),
    CONSTRAINT ck_salidas_anulacion CHECK (anulada = FALSE OR corrige_a IS NOT NULL)
) ENGINE=InnoDB;
