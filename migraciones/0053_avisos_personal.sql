-- Avisos para el personal: correcciones y retiro solo por INSERT (ADR 0003).
CREATE TABLE avisos_personal (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    texto VARCHAR(200) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    KEY ix_avisos_personal_socio_fecha (socio_id, registrado_en, id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;
