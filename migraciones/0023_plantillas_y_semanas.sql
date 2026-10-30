-- La semana tipo se publica como una secuencia completa e inmutable.
ALTER TABLE programas_entrenamiento ADD COLUMN duracion_semanas INT NULL;
ALTER TABLE sesiones_planificadas ADD COLUMN semana INT NULL;

CREATE TABLE plantillas_programa (
    id BINARY(16) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(500) NOT NULL,
    creada_en DATETIME(6) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE plantillas_sesiones (
    id BINARY(16) NOT NULL PRIMARY KEY,
    plantilla_id BINARY(16) NOT NULL,
    posicion INT NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    UNIQUE KEY uq_plantilla_posicion (plantilla_id, posicion),
    FOREIGN KEY (plantilla_id) REFERENCES plantillas_programa(id)
) ENGINE=InnoDB;

CREATE TABLE plantillas_ejercicios (
    id BINARY(16) NOT NULL PRIMARY KEY,
    sesion_id BINARY(16) NOT NULL,
    ejercicio_id BINARY(16) NOT NULL,
    posicion INT NOT NULL,
    series INT NOT NULL,
    repeticiones_minimas INT NULL,
    repeticiones_maximas INT NULL,
    rir_objetivo INT NULL,
    descanso INT NULL,
    duracion INT NULL,
    distancia DECIMAL(10,2) NULL,
    UNIQUE KEY uq_plantilla_ejercicio_posicion (sesion_id, posicion),
    FOREIGN KEY (sesion_id) REFERENCES plantillas_sesiones(id),
    FOREIGN KEY (ejercicio_id) REFERENCES ejercicios(id)
) ENGINE=InnoDB;
