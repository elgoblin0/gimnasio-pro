-- Consultas de ficha: hechos que solo se agregan (ADR 0003 y 0010).
CREATE TABLE consultas_ficha (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    consultado_por BINARY(16) NOT NULL,
    registrada_en DATETIME(6) NOT NULL,
    KEY ix_consultas_socio_fecha (socio_id, registrada_en, id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (consultado_por) REFERENCES usuarios(id)
) ENGINE=InnoDB;
