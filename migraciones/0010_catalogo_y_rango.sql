-- Catálogo estructurado y prescripción con rango; conserva las repeticiones existentes.
ALTER TABLE ejercicios
    ADD COLUMN patron_movimiento VARCHAR(60) NOT NULL DEFAULT '',
    ADD COLUMN equipo VARCHAR(60) NOT NULL DEFAULT '',
    ADD COLUMN incremento_carga DECIMAL(5,2) NULL;

CREATE TABLE IF NOT EXISTS zonas_ejercicio (
    ejercicio_id BINARY(16) NOT NULL,
    zona VARCHAR(30) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    PRIMARY KEY (ejercicio_id, zona),
    FOREIGN KEY (ejercicio_id) REFERENCES ejercicios (id),
    CONSTRAINT ck_zonas_ejercicio CHECK (zona IN ('pecho', 'espalda_alta', 'dorsales', 'hombros', 'biceps', 'triceps', 'abdomen', 'gluteos', 'cuadriceps', 'isquiotibiales', 'pantorrillas', 'zona_lumbar', 'rodillas', 'cuello'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS alternativas_ejercicio (
    ejercicio_id BINARY(16) NOT NULL,
    alternativa_id BINARY(16) NOT NULL,
    orden INT NOT NULL,
    PRIMARY KEY (ejercicio_id, alternativa_id),
    FOREIGN KEY (ejercicio_id) REFERENCES ejercicios (id),
    FOREIGN KEY (alternativa_id) REFERENCES ejercicios (id),
    CONSTRAINT ck_alternativas_distintas CHECK (ejercicio_id <> alternativa_id)
) ENGINE=InnoDB;

ALTER TABLE ejercicios_planificados
    ADD COLUMN repeticiones_minimas INT NULL,
    ADD COLUMN repeticiones_maximas INT NULL,
    ADD COLUMN rir_objetivo INT NULL,
    ADD COLUMN descanso INT NULL;
UPDATE ejercicios_planificados
    SET repeticiones_minimas = repeticiones, repeticiones_maximas = repeticiones;
ALTER TABLE ejercicios_planificados
    DROP CHECK ck_planificados_repeticiones,
    DROP COLUMN repeticiones,
    ADD CONSTRAINT ck_planificados_rango CHECK (repeticiones_minimas <= repeticiones_maximas),
    ADD CONSTRAINT ck_planificados_minimas CHECK (repeticiones_minimas > 0),
    ADD CONSTRAINT ck_planificados_maximas CHECK (repeticiones_maximas > 0),
    ADD CONSTRAINT ck_planificados_rir CHECK (rir_objetivo BETWEEN 0 AND 5);
