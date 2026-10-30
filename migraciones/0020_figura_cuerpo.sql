-- Figura del cuerpo 3D que eligió cada persona (ADR 0020). NULL: todavía no eligió.
ALTER TABLE personas ADD COLUMN figura_cuerpo ENUM('masculina', 'femenina') NULL;
