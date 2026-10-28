-- Sustituciones: hechos que acreditan el ejercicio planificado (#84).
CREATE TABLE IF NOT EXISTS sustituciones (
    id BINARY(16) NOT NULL PRIMARY KEY,
    sesion_realizada_id BINARY(16) NOT NULL,
    ejercicio_planificado_id BINARY(16) NOT NULL,
    ejercicio_hecho_id BINARY(16) NOT NULL,
    motivo VARCHAR(32) NOT NULL,
    autor_id BINARY(16) NOT NULL,
    registrada_en DATETIME(6) NOT NULL,
    KEY ix_sustituciones_vigentes (sesion_realizada_id, ejercicio_planificado_id, registrada_en, id),
    CONSTRAINT fk_sustituciones_sesion FOREIGN KEY (sesion_realizada_id) REFERENCES sesiones_realizadas (id),
    CONSTRAINT fk_sustituciones_planificado FOREIGN KEY (ejercicio_planificado_id) REFERENCES ejercicios_planificados (id),
    CONSTRAINT fk_sustituciones_hecho FOREIGN KEY (ejercicio_hecho_id) REFERENCES ejercicios (id),
    CONSTRAINT fk_sustituciones_autor FOREIGN KEY (autor_id) REFERENCES usuarios (id),
    CONSTRAINT ck_sustituciones_motivo CHECK (motivo IN ('maquina_ocupada', 'dolor_reportado', 'restriccion_salud'))
);
