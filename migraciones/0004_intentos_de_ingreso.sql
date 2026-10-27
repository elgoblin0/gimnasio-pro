-- Intentos de inicio de sesión, para limitar los fallidos por identificador y por IP (ADR 0006).
CREATE TABLE IF NOT EXISTS intentos_de_ingreso (
    id BINARY(16) NOT NULL PRIMARY KEY,
    identificador VARCHAR(160) NOT NULL,
    ip VARCHAR(45) NOT NULL,
    exitoso BOOLEAN NOT NULL,
    ocurrido_en DATETIME(6) NOT NULL,
    KEY ix_intentos_identificador (identificador, ocurrido_en),
    KEY ix_intentos_ip (ip, ocurrido_en)
);
