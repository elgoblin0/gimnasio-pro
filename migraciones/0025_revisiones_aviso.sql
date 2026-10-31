-- Revisar un aviso agrega una constancia; nunca cambia el freno.
CREATE TABLE IF NOT EXISTS revisiones_aviso (
    id BINARY(16) NOT NULL PRIMARY KEY,
    aviso_id BINARY(16) NOT NULL,
    entrenador_id BINARY(16) NOT NULL,
    nota VARCHAR(500) NULL,
    revisada_en DATETIME(6) NOT NULL,
    UNIQUE KEY uq_revision_aviso (aviso_id),
    FOREIGN KEY (aviso_id) REFERENCES avisos_entrenador(id),
    FOREIGN KEY (entrenador_id) REFERENCES usuarios(id)
);
