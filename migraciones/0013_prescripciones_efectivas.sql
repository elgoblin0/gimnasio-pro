-- Prescripción efectiva inmutable al empezar la sesión (ADR 0003 y 0012).
CREATE TABLE prescripciones_efectivas (
    id BINARY(16) PRIMARY KEY,
    sesion_realizada_id BINARY(16) NOT NULL UNIQUE,
    version_reglas VARCHAR(20) NOT NULL,
    creada_en DATETIME(6) NOT NULL,
    ejercicios JSON NOT NULL,
    explicacion JSON NOT NULL,
    frenos JSON NOT NULL,
    FOREIGN KEY (sesion_realizada_id) REFERENCES sesiones_realizadas(id)
) ENGINE=InnoDB;
