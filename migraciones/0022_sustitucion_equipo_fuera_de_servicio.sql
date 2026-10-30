-- Issue #177: ampliar solo los motivos admitidos, sin modificar hechos.
ALTER TABLE sustituciones
    DROP CHECK ck_sustituciones_motivo,
    ADD CONSTRAINT ck_sustituciones_motivo CHECK (
        motivo IN ('maquina_ocupada', 'dolor_reportado', 'restriccion_salud', 'equipo_fuera_de_servicio')
    );
