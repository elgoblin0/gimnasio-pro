-- Registro técnico de reintentos; no modifica tablas de hechos (ADR 0004 y 0008).
CREATE TABLE IF NOT EXISTS solicitudes_idempotentes (
    clave BINARY(16) NOT NULL,
    usuario_id BINARY(16) NOT NULL,
    huella_cuerpo BINARY(32) NOT NULL,
    estado_http SMALLINT UNSIGNED NOT NULL,
    respuesta LONGBLOB NOT NULL,
    creada_en DATETIME(6) NOT NULL,
    PRIMARY KEY (usuario_id, clave),
    KEY ix_solicitudes_idempotentes_creada_en (creada_en),
    CONSTRAINT fk_solicitudes_idempotentes_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
) ENGINE=InnoDB;
