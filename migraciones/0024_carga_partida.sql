ALTER TABLE ejercicios_planificados
    ADD COLUMN carga_partida DECIMAL(8,2) NULL,
    ADD CONSTRAINT carga_partida_no_negativa CHECK (carga_partida >= 0);
