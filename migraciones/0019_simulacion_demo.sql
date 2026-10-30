ALTER TABLE personas ADD COLUMN simulada BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE simulacion_demo (
    unica BOOLEAN NOT NULL DEFAULT TRUE PRIMARY KEY,
    generada_hasta DATETIME(6) NOT NULL,
    CONSTRAINT simulacion_demo_unica CHECK (unica = TRUE)
);
