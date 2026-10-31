-- Tipos configurables y pagos registrados que renuevan la membresía (#213).
CREATE TABLE tipos_membresia (
    id BINARY(16) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    duracion_dias INT UNSIGNED NOT NULL,
    precio BIGINT UNSIGNED NOT NULL,
    archivado BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en DATETIME(6) NOT NULL,
    actualizado_en DATETIME(6) NOT NULL,
    CONSTRAINT ck_tipos_membresia_duracion CHECK (duracion_dias > 0)
);

CREATE TABLE pagos (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    tipo_id BINARY(16) NOT NULL,
    medio ENUM('efectivo', 'transferencia', 'tarjeta', 'otro') NOT NULL,
    monto BIGINT UNSIGNED NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    CONSTRAINT fk_pagos_socio FOREIGN KEY (socio_id) REFERENCES usuarios (id),
    CONSTRAINT fk_pagos_tipo FOREIGN KEY (tipo_id) REFERENCES tipos_membresia (id),
    CONSTRAINT fk_pagos_autor FOREIGN KEY (autor_id) REFERENCES usuarios (id)
);

-- La membresía es estado derivado; no pertenece a HECHOS (decisión de Opus, ADR 0027).
ALTER TABLE membresias
    ADD COLUMN pago_id BINARY(16) NULL,
    ADD COLUMN tipo_id BINARY(16) NULL,
    ADD UNIQUE KEY uq_membresias_pago (pago_id),
    ADD CONSTRAINT fk_membresias_pago FOREIGN KEY (pago_id) REFERENCES pagos (id),
    ADD CONSTRAINT fk_membresias_tipo FOREIGN KEY (tipo_id) REFERENCES tipos_membresia (id);
