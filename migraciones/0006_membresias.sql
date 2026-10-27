-- Acceso sin cupo de entradas; vigencia inclusiva por fecha local de la sede (#36).
CREATE TABLE IF NOT EXISTS membresias (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    desde DATE NOT NULL,
    hasta DATE NOT NULL,
    actualizada_en DATETIME(6) NOT NULL,
    KEY ix_membresias_socio_vigencia (socio_id, desde, hasta),
    CONSTRAINT fk_membresias_socio FOREIGN KEY (socio_id) REFERENCES usuarios (id),
    CONSTRAINT ck_membresias_vigencia CHECK (hasta >= desde)
);
