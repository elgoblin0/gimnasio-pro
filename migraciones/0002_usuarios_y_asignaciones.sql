-- Usuarios con un rol cada uno (ADR 0006) y asignación de socios a entrenadores.
CREATE TABLE IF NOT EXISTS usuarios (
    id BINARY(16) NOT NULL PRIMARY KEY,
    persona_id BINARY(16) NOT NULL,
    rol ENUM('socio', 'recepcion', 'entrenador', 'administracion') NOT NULL,
    -- NULL: el usuario no puede entrar con clave (por ejemplo, los usuarios de la demo).
    clave_hash VARCHAR(255) NULL,
    es_demo BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en DATETIME(6) NOT NULL,
    actualizado_en DATETIME(6) NOT NULL,
    UNIQUE KEY uq_usuarios_persona (persona_id),
    KEY ix_usuarios_demo (es_demo, rol),
    CONSTRAINT fk_usuarios_persona FOREIGN KEY (persona_id) REFERENCES personas (id)
);

-- Una asignación vigente tiene `hasta` en NULL. Cambiar de entrenador cierra la anterior y abre otra.
CREATE TABLE IF NOT EXISTS asignaciones_entrenador (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    entrenador_id BINARY(16) NOT NULL,
    desde DATETIME(6) NOT NULL,
    hasta DATETIME(6) NULL,
    KEY ix_asignaciones_entrenador (entrenador_id, hasta),
    KEY ix_asignaciones_socio (socio_id, hasta),
    CONSTRAINT fk_asignaciones_socio FOREIGN KEY (socio_id) REFERENCES usuarios (id),
    CONSTRAINT fk_asignaciones_entrenador FOREIGN KEY (entrenador_id) REFERENCES usuarios (id)
);
