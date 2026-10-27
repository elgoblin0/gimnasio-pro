-- Programa de entrenamiento versionado y sesiones planificadas independientes de lo realizado.
-- UUIDv7 en BINARY(16); fechas UTC. Carga en kg, duración en segundos y distancia en metros.
CREATE TABLE IF NOT EXISTS ejercicios (
    id BINARY(16) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    medidas_aplicables JSON NOT NULL,
    actualizada_en DATETIME(6) NOT NULL,
    CONSTRAINT ck_ejercicios_medidas CHECK (JSON_TYPE(medidas_aplicables) = 'ARRAY')
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS programas_entrenamiento (
    id BINARY(16) NOT NULL PRIMARY KEY,
    socio_id BINARY(16) NOT NULL,
    version INT NOT NULL,
    creado_en DATETIME(6) NOT NULL,
    UNIQUE KEY uq_programas_socio_version (socio_id, version),
    CONSTRAINT fk_programas_socio FOREIGN KEY (socio_id) REFERENCES usuarios (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sesiones_planificadas (
    id BINARY(16) NOT NULL PRIMARY KEY,
    programa_id BINARY(16) NOT NULL,
    posicion INT NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    UNIQUE KEY uq_sesiones_programa_posicion (programa_id, posicion),
    CONSTRAINT fk_sesiones_programa FOREIGN KEY (programa_id) REFERENCES programas_entrenamiento (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ejercicios_planificados (
    id BINARY(16) NOT NULL PRIMARY KEY,
    sesion_planificada_id BINARY(16) NOT NULL,
    ejercicio_id BINARY(16) NOT NULL,
    posicion INT NOT NULL,
    series INT NOT NULL,
    repeticiones INT NULL,
    carga DECIMAL(8,2) NULL,
    duracion INT NULL,
    distancia DECIMAL(10,2) NULL,
    UNIQUE KEY uq_ejercicios_sesion_posicion (sesion_planificada_id, posicion),
    CONSTRAINT fk_planificados_sesion FOREIGN KEY (sesion_planificada_id) REFERENCES sesiones_planificadas (id),
    CONSTRAINT fk_planificados_ejercicio FOREIGN KEY (ejercicio_id) REFERENCES ejercicios (id),
    CONSTRAINT ck_planificados_series CHECK (series > 0),
    CONSTRAINT ck_planificados_repeticiones CHECK (repeticiones > 0),
    CONSTRAINT ck_planificados_carga CHECK (carga >= 0),
    CONSTRAINT ck_planificados_duracion CHECK (duracion > 0),
    CONSTRAINT ck_planificados_distancia CHECK (distancia > 0)
) ENGINE=InnoDB;
