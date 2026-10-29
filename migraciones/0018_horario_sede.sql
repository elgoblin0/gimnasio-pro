-- Horario semanal local por día ISO; también válido para una sede ya cargada.
ALTER TABLE sedes ADD COLUMN horario JSON NOT NULL DEFAULT (JSON_OBJECT(
    '1', JSON_ARRAY(JSON_ARRAY('06:00', '22:00')),
    '2', JSON_ARRAY(JSON_ARRAY('06:00', '22:00')),
    '3', JSON_ARRAY(JSON_ARRAY('06:00', '22:00')),
    '4', JSON_ARRAY(JSON_ARRAY('06:00', '22:00')),
    '5', JSON_ARRAY(JSON_ARRAY('06:00', '22:00')),
    '6', JSON_ARRAY(JSON_ARRAY('08:00', '14:00'))
));
