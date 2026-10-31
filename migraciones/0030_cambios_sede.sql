-- Historial de configuración; no modifica hechos existentes.
CREATE TABLE cambios_sede (
    id BINARY(16) PRIMARY KEY,
    sede_id BINARY(16) NOT NULL,
    aforo_maximo INT NOT NULL,
    horario JSON NOT NULL,
    motivo VARCHAR(500) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    FOREIGN KEY (sede_id) REFERENCES sedes(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id),
    CHECK (aforo_maximo > 0),
    INDEX historial_sede (sede_id, registrado_en, id)
);
