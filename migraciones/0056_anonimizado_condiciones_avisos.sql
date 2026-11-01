-- Autoriza Opus: #229
-- Completa 0054: condiciones, descripción de restricciones y avisos para el personal anonimizables (ADR 0025).
ALTER TABLE condiciones_salud
    ADD COLUMN anonimizada BOOLEAN NOT NULL DEFAULT FALSE,
    MODIFY COLUMN descripcion VARCHAR(1000) NULL,
    ADD CONSTRAINT ck_condiciones_anonimizada CHECK ((descripcion IS NULL) = anonimizada);

ALTER TABLE restricciones_salud
    MODIFY COLUMN descripcion TEXT NULL,
    ADD CONSTRAINT ck_restricciones_descripcion CHECK ((descripcion IS NULL) = anonimizada);

ALTER TABLE avisos_personal
    ADD COLUMN anonimizada BOOLEAN NOT NULL DEFAULT FALSE,
    MODIFY COLUMN texto VARCHAR(200) NULL,
    ADD CONSTRAINT ck_avisos_personal_anonimizado CHECK ((texto IS NULL) = anonimizada);
