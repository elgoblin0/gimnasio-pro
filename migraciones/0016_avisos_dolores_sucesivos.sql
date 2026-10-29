-- Cada dolor reportado deja un aviso, incluso en la misma sesión (#89, revisión de Opus en #119).
-- Los llamadores conservan la idempotencia por prescripción efectiva o dolor reportado.
ALTER TABLE avisos_entrenador
    ADD KEY ix_aviso_freno (sesion_realizada_id, freno),
    DROP INDEX uq_aviso_freno;
