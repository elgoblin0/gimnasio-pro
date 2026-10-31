-- Las plantillas son editables; los programas publicados conservan su copia.
ALTER TABLE plantillas_programa ADD COLUMN archivada BOOLEAN NOT NULL DEFAULT FALSE;
