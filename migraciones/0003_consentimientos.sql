-- Consentimientos: tabla de hechos, solo INSERT (ADR 0003). Otorgar y revocar son registros nuevos;
-- el estado vigente de un tipo es el último registro del socio para ese tipo (ADR 0006 y 0010).
CREATE TABLE IF NOT EXISTS consentimientos (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    tipo ENUM('datos_personales', 'salud', 'imagen') NOT NULL,
    version_texto VARCHAR(20) NOT NULL,
    otorgado BOOLEAN NOT NULL,
    registrado_por BINARY(16) NOT NULL,
    registrado_en DATETIME(6) NOT NULL,
    KEY ix_consentimientos_vigente (socio_id, tipo, registrado_en),
    CONSTRAINT fk_consentimientos_socio FOREIGN KEY (socio_id) REFERENCES usuarios (id),
    CONSTRAINT fk_consentimientos_autor FOREIGN KEY (registrado_por) REFERENCES usuarios (id)
);
