-- Anulaciones como hechos nuevos; conserva pagos y membresías anteriores.
CREATE TABLE anulaciones_pago (
    id BINARY(16) PRIMARY KEY,
    pago_id BINARY(16) NOT NULL UNIQUE,
    motivo VARCHAR(500) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    FOREIGN KEY (pago_id) REFERENCES pagos(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id),
    CHECK (CHAR_LENGTH(TRIM(motivo)) > 0)
);
