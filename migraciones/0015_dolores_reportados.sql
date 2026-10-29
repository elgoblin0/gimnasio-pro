-- Dolor reportado: hechos de solo inserción, con un único origen (#89).
CREATE TABLE IF NOT EXISTS dolores_reportados (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    zona VARCHAR(32) NOT NULL,
    origen VARCHAR(16) NOT NULL,
    chequeo_id BINARY(16) NULL,
    sesion_realizada_id BINARY(16) NULL,
    registrado_en DATETIME(6) NOT NULL,
    KEY ix_dolores_chequeo (chequeo_id),
    KEY ix_dolores_sesion (sesion_realizada_id),
    FOREIGN KEY (socio_id) REFERENCES usuarios(id),
    FOREIGN KEY (chequeo_id) REFERENCES chequeos_dia(id),
    FOREIGN KEY (sesion_realizada_id) REFERENCES sesiones_realizadas(id),
    CHECK (zona IN ('pecho','espalda_alta','dorsales','hombros','biceps','triceps','abdomen',
                   'gluteos','cuadriceps','isquiotibiales','pantorrillas','zona_lumbar','rodillas','cuello')),
    CHECK ((origen = 'chequeo' AND chequeo_id IS NOT NULL AND sesion_realizada_id IS NULL)
        OR (origen = 'sesion' AND sesion_realizada_id IS NOT NULL AND chequeo_id IS NULL))
);
