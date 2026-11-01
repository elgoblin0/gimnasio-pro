CREATE TABLE condiciones_salud (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    descripcion VARCHAR(1000) NOT NULL,
    reemplaza_a BINARY(16) NULL UNIQUE,
    registrada_en DATETIME(6) NOT NULL,
    KEY ix_condiciones_socio (socio_id, registrada_en, id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (reemplaza_a) REFERENCES condiciones_salud(id)
);

CREATE TABLE revisiones_condicion (
    id BINARY(16) NOT NULL PRIMARY KEY,
    condicion_id BINARY(16) NOT NULL UNIQUE,
    autor_id BINARY(16) NOT NULL,
    nota VARCHAR(1000) NULL,
    registrada_en DATETIME(6) NOT NULL,
    FOREIGN KEY (condicion_id) REFERENCES condiciones_salud(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id)
);
