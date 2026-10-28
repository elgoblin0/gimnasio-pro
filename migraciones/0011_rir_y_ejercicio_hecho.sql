-- Agrega datos opcionales sin reescribir hechos (ADR 0003 y 0012).
ALTER TABLE series_realizadas
 ADD COLUMN rir TINYINT NULL,
 ADD COLUMN ejercicio_hecho_id BINARY(16) NULL,
 ADD CONSTRAINT chk_series_rir CHECK (rir BETWEEN 0 AND 10),
 ADD CONSTRAINT fk_series_ejercicio_hecho FOREIGN KEY (ejercicio_hecho_id) REFERENCES ejercicios(id);
