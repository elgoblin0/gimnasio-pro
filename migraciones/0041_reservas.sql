CREATE TABLE reservas (
    id BINARY(16) PRIMARY KEY,
    ocurrencia_id BINARY(16) NOT NULL,
    socio_id BINARY(16) NOT NULL,
    solicitada_en DATETIME(6) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    FOREIGN KEY (ocurrencia_id) REFERENCES ocurrencias_clase(id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id),
    INDEX (ocurrencia_id, solicitada_en, id),
    INDEX (socio_id, ocurrencia_id)
);

CREATE TABLE cancelaciones_reserva (
    id BINARY(16) PRIMARY KEY,
    reserva_id BINARY(16) NOT NULL UNIQUE,
    autor_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    FOREIGN KEY (reserva_id) REFERENCES reservas(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id)
);
