CREATE TABLE cancelaciones_ocurrencia (
    id BINARY(16) PRIMARY KEY,
    ocurrencia_id BINARY(16) NOT NULL UNIQUE,
    motivo TEXT NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    FOREIGN KEY (ocurrencia_id) REFERENCES ocurrencias_clase(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id)
);

CREATE TABLE avisos_socio (
    id BINARY(16) PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    ocurrencia_id BINARY(16) NOT NULL,
    tipo ENUM('paso_a_tener_lugar', 'volvio_a_espera', 'ocurrencia_cancelada') NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (ocurrencia_id) REFERENCES ocurrencias_clase(id),
    INDEX (socio_id, registrado_en, id)
);

CREATE TABLE vistos_aviso_socio (
    id BINARY(16) PRIMARY KEY,
    aviso_id BINARY(16) NOT NULL UNIQUE,
    registrado_en DATETIME(6) NOT NULL,
    FOREIGN KEY (aviso_id) REFERENCES avisos_socio(id)
);

CREATE TABLE cupos_ocurrencia (
    id BINARY(16) PRIMARY KEY,
    ocurrencia_id BINARY(16) NOT NULL UNIQUE,
    cupo INT NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    FOREIGN KEY (ocurrencia_id) REFERENCES ocurrencias_clase(id),
    CHECK (cupo > 0)
);
