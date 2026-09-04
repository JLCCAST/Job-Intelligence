-- =========================================================
-- AI Job Intelligence & Career Analytics Platform
-- =========================================================

-- --------- Catálogos ---------

CREATE TABLE status (
    status_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre          VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE source (
    source_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE company (
    company_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre          VARCHAR(200) NOT NULL UNIQUE
);


CREATE TABLE technology (
    technology_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_canonico VARCHAR(100) NOT NULL UNIQUE,
    categoria       VARCHAR(50) NOT NULL
);

CREATE TABLE technology_alias (
    alias_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    technology_id   INTEGER NOT NULL REFERENCES technology(technology_id),
    alias_texto     VARCHAR(100) NOT NULL UNIQUE
);

-- --------- Núcleo: ofertas laborales ---------

CREATE TABLE job (
    job_id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id          INTEGER NOT NULL REFERENCES company(company_id),
    source_id           INTEGER NOT NULL REFERENCES source(source_id),
    status_id           INTEGER NOT NULL REFERENCES status(status_id),
    puesto              VARCHAR(200) NOT NULL,
    url                 VARCHAR(1000),
    fecha_publicacion   DATE,
    fecha_registro      TIMESTAMPTZ NOT NULL DEFAULT now(),
    area                VARCHAR(50),
    modalidad           VARCHAR(30),   
    ubicacion           VARCHAR(150),
    ingles_requerido    VARCHAR(30),   
    descripcion_raw     TEXT,
    descripcion_limpia  TEXT,
    match_score         NUMERIC(5,2)
);

CREATE TABLE job_status_history (
    history_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id          INTEGER NOT NULL REFERENCES job(job_id),
    status_id       INTEGER NOT NULL REFERENCES status(status_id),
    fecha           TIMESTAMPTZ NOT NULL DEFAULT now(),
    nota            VARCHAR(500)
);

-- --------- Relación oferta <-> tecnología (con contexto) ---------

CREATE TABLE job_technology (
    job_id              INTEGER NOT NULL REFERENCES job(job_id),
    technology_id       INTEGER NOT NULL REFERENCES technology(technology_id),
    requirement_type    VARCHAR(20) NOT NULL CHECK (requirement_type IN ('required', 'preferred')),
    level               VARCHAR(20),      
    confidence          NUMERIC(4,3),     
    evidence_text       VARCHAR(500),     
    PRIMARY KEY (job_id, technology_id)
);

-- --------- Tu propio perfil de habilidades ---------

CREATE TABLE user_skill (
    technology_id       INTEGER PRIMARY KEY REFERENCES technology(technology_id),
    level               VARCHAR(20) NOT NULL,  
    meses_experiencia   INTEGER,
    evidencia           VARCHAR(300)            
);

-- =========================================================
-- Datos iniciales
-- =========================================================

INSERT INTO status (nombre) VALUES
    ('Registrada'), ('Analizada'), ('Postulada'),
    ('Entrevista'), ('Oferta'), ('Rechazada'), ('Descartada');

INSERT INTO source (nombre) VALUES
    ('LinkedIn'), ('Indeed'), ('Computrabajo'),
    ('Bumeran'), ('Career Page'), ('Otro');
