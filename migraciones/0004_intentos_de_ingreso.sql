-- Intentos de inicio de sesión, para limitar los fallidos por usuario y por IP (ADR 0006).
-- `usuario_id` queda en NULL cuando el identificador no corresponde a ningún usuario.
CREATE TABLE IF NOT EXISTS intentos_de_ingreso (
    id BINARY(16) NOT NULL PRIMARY KEY,
    usuario_id BINARY(16) NULL,
    identificador VARCHAR(160) NOT NULL,
    ip VARCHAR(45) NOT NULL,
    exitoso BOOLEAN NOT NULL,
    ocurrido_en DATETIME(6) NOT NULL,
    KEY ix_intentos_usuario (usuario_id, ocurrido_en),
    KEY ix_intentos_identificador (identificador, ocurrido_en),
    KEY ix_intentos_ip (ip, ocurrido_en)
);
