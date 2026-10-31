-- Autoriza Opus: #228
-- Estado anonimizado para el borrado de datos de salud, única excepción al historial que solo agrega (ADR 0025).
ALTER TABLE restricciones_salud
    ADD COLUMN anonimizada BOOLEAN NOT NULL DEFAULT FALSE,
    DROP CHECK restricciones_salud_chk_1,
    ADD CONSTRAINT ck_restricciones_objetivo CHECK (
        (NOT anonimizada AND (ejercicio_id IS NOT NULL) + (patron_movimiento IS NOT NULL) + (zona IS NOT NULL) = 1)
        OR (anonimizada AND ejercicio_id IS NULL AND patron_movimiento IS NULL AND zona IS NULL)
    );

ALTER TABLE dolores_reportados
    ADD COLUMN anonimizada BOOLEAN NOT NULL DEFAULT FALSE,
    MODIFY COLUMN zona VARCHAR(32) NULL,
    ADD CONSTRAINT ck_dolores_anonimizado CHECK ((zona IS NULL) = anonimizada);

CREATE TABLE IF NOT EXISTS borrados_salud (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    KEY ix_borrados_salud_socio (socio_id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id)
);
