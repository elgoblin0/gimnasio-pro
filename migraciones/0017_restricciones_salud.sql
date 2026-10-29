-- Restricciones ficticias: altas y bajas por INSERT, sin API de escritura (#90).
CREATE TABLE IF NOT EXISTS restricciones_salud (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    ejercicio_id BINARY(16) NULL,
    patron_movimiento VARCHAR(64) NULL,
    zona VARCHAR(32) NULL,
    descripcion TEXT NOT NULL,
    registrada_en DATETIME(6) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    levanta_a BINARY(16) NULL,
    KEY ix_restricciones_socio (socio_id, registrada_en, id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (ejercicio_id) REFERENCES ejercicios(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id),
    FOREIGN KEY (levanta_a) REFERENCES restricciones_salud(id),
    CHECK ((ejercicio_id IS NOT NULL) + (patron_movimiento IS NOT NULL) + (zona IS NOT NULL) = 1),
    CHECK (zona IS NULL OR zona IN ('pecho','espalda_alta','dorsales','hombros','biceps','triceps','abdomen',
        'gluteos','cuadriceps','isquiotibiales','pantorrillas','zona_lumbar','rodillas','cuello'))
);
