-- Estado actualizable del perfil de entrenamiento, separado de salud (ADR 0026).
CREATE TABLE perfiles_entrenamiento (
    socio_id BINARY(16) NOT NULL PRIMARY KEY,
    objetivo VARCHAR(500) NULL,
    experiencia ENUM('inicial', 'intermedia', 'avanzada') NULL,
    disponibilidad_semanal TINYINT UNSIGNED NULL,
    tiempo_por_sesion SMALLINT UNSIGNED NULL,
    preferencias VARCHAR(500) NULL,
    actualizado_en DATETIME(6) NOT NULL,
    actualizado_por BINARY(16) NOT NULL,
    CONSTRAINT fk_perfil_socio FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    CONSTRAINT fk_perfil_autor FOREIGN KEY (actualizado_por) REFERENCES usuarios(id),
    CONSTRAINT ck_perfil_disponibilidad CHECK (disponibilidad_semanal BETWEEN 1 AND 7),
    CONSTRAINT ck_perfil_tiempo CHECK (tiempo_por_sesion BETWEEN 15 AND 240)
);
