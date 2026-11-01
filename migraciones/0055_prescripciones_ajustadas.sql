-- Prescripción ajustada por dolor reportado en la sesión: hecho de solo inserción (ADR 0003 y 0030).
-- La vigente es la última de la sesión; la lee el servicio cuando el socio no tiene consentimiento de salud.
CREATE TABLE prescripciones_ajustadas (
    id BINARY(16) PRIMARY KEY,
    sesion_realizada_id BINARY(16) NOT NULL,
    version_reglas VARCHAR(20) NOT NULL,
    creada_en DATETIME(6) NOT NULL,
    ejercicios JSON NOT NULL,
    explicacion JSON NOT NULL,
    KEY ix_prescripciones_ajustadas_sesion (sesion_realizada_id, creada_en, id),
    FOREIGN KEY (sesion_realizada_id) REFERENCES sesiones_realizadas(id)
) ENGINE=InnoDB;
