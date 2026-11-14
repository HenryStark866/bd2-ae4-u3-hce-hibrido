-- =====================================================================
-- 01_postgres_esquema.sql  -  Capa ACID de la arquitectura hibrida
-- HCE Basica Antioquia / Subsistema de Hospitalizacion  (PostgreSQL 16+; probado en 17.11)
-- Ejecutar: psql -U postgres -d hce_hibrido -f scripts/01_postgres_esquema.sql
--
-- Que vive aqui (y por que):
--   identidad del paciente, profesionales, catalogos, camas, hospitalizaciones
--   y el registro de dispositivos. Son datos de registro (System of Record):
--   pocos, muy consultados y donde un error es inaceptable (dos pacientes en
--   la misma cama, un dispositivo asignado a quien no es). Necesitan claves
--   foraneas, unicidad y transacciones atomicas.
--   La telemetria de sensores, wearables y los eventos de teleconsulta van a
--   MongoDB (capa BASE): ver 03_mongo_esquema.js.
--   La tabla telemetria_jsonb NO es parte de la arquitectura propuesta: existe
--   solo para comparar la misma ingesta en PostgreSQL (JSONB, como el insumo
--   del curso) frente a MongoDB.
-- =====================================================================
DROP SCHEMA IF EXISTS hce CASCADE;
CREATE SCHEMA hce;
SET search_path TO hce;

-- ---------- Catalogos ----------
CREATE TABLE cie10 (
  codigo        VARCHAR(8)  PRIMARY KEY,
  descripcion   TEXT        NOT NULL,
  capitulo      VARCHAR(40) NOT NULL,
  notificacion_obligatoria BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE medicamento (
  medicamento_id  VARCHAR(10) PRIMARY KEY,
  nombre_generico VARCHAR(80) NOT NULL,
  atc             CHAR(7)     NOT NULL CHECK (atc ~ '^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$'),
  forma           VARCHAR(40),
  concentracion   VARCHAR(40),
  familia_alergia VARCHAR(20)
);

-- ---------- Identidad (dato sensible: Ley 1581 de 2012) ----------
CREATE TABLE paciente (
  paciente_id      VARCHAR(10) PRIMARY KEY,
  tipo_documento   VARCHAR(2)  NOT NULL CHECK (tipo_documento IN ('CC','TI','RC','CE','PA')),
  documento        VARCHAR(15) NOT NULL CHECK (documento ~ '^[0-9A-Z]{5,15}$'),
  nombres          VARCHAR(60) NOT NULL,
  apellidos        VARCHAR(60) NOT NULL,
  fecha_nacimiento DATE        NOT NULL CHECK (fecha_nacimiento > DATE '1900-01-01'),
  sexo             CHAR(1)     NOT NULL CHECK (sexo IN ('F','M','I')),
  grupo_sanguineo  VARCHAR(3),
  municipio        VARCHAR(60) NOT NULL,
  subregion        VARCHAR(30) NOT NULL,
  eps              VARCHAR(60) NOT NULL,
  regimen          VARCHAR(12) NOT NULL CHECK (regimen IN ('CONTRIBUTIVO','SUBSIDIADO','ESPECIAL')),
  creado_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ux_paciente_documento UNIQUE (tipo_documento, documento)
);

CREATE TABLE paciente_alergia (
  paciente_id VARCHAR(10) REFERENCES paciente ON DELETE CASCADE,
  alergia     VARCHAR(40),
  PRIMARY KEY (paciente_id, alergia)
);

CREATE TABLE profesional (
  profesional_id  VARCHAR(10) PRIMARY KEY,
  nombre          VARCHAR(80) NOT NULL,
  rol             VARCHAR(12) NOT NULL CHECK (rol IN ('MEDICO','ENFERMERIA','ESPECIALISTA')),
  especialidad    VARCHAR(60),
  registro_medico VARCHAR(20) NOT NULL UNIQUE
);

-- ---------- Capacidad y episodios ----------
CREATE TABLE cama (
  cama_id  VARCHAR(10) PRIMARY KEY,
  ips      VARCHAR(80) NOT NULL,
  servicio VARCHAR(20) NOT NULL CHECK (servicio IN ('MEDICINA_INTERNA','PEDIATRIA','CIRUGIA','GINECOOBSTETRICIA','UCI')),
  estado   VARCHAR(14) NOT NULL CHECK (estado IN ('DISPONIBLE','OCUPADA','MANTENIMIENTO'))
);

CREATE TABLE hospitalizacion (
  hospitalizacion_id VARCHAR(16) PRIMARY KEY,
  paciente_id        VARCHAR(10) NOT NULL REFERENCES paciente,
  medico_tratante_id VARCHAR(10) NOT NULL REFERENCES profesional,
  cama_id            VARCHAR(10) NOT NULL REFERENCES cama,
  servicio           VARCHAR(20) NOT NULL,
  fecha_admision     TIMESTAMPTZ NOT NULL,
  fecha_egreso       TIMESTAMPTZ,
  dx_principal       VARCHAR(8)  REFERENCES cie10,
  estado             VARCHAR(10) NOT NULL CHECK (estado IN ('ACTIVA','EGRESADA')),
  CHECK (fecha_egreso IS NULL OR fecha_egreso > fecha_admision),
  CHECK ((estado = 'ACTIVA') = (fecha_egreso IS NULL))
);
-- Regla de negocio que solo una capa ACID garantiza: una cama no puede tener
-- dos hospitalizaciones activas, ni un paciente dos ingresos activos a la vez.
CREATE UNIQUE INDEX ux_cama_activa     ON hospitalizacion (cama_id)     WHERE estado = 'ACTIVA';
CREATE UNIQUE INDEX ux_paciente_activo ON hospitalizacion (paciente_id) WHERE estado = 'ACTIVA';
CREATE INDEX ix_hosp_servicio_estado   ON hospitalizacion (servicio, estado);

-- ---------- Registro de dispositivos (puente entre las dos capas) ----------
-- Cada lectura en MongoDB trae el dispositivo_id; aqui se sabe a quien y a que
-- episodio estaba asignado. Cambiar la asignacion es una transaccion ACID.
CREATE TABLE dispositivo (
  dispositivo_id VARCHAR(12) PRIMARY KEY,
  tipo           VARCHAR(24) NOT NULL CHECK (tipo IN ('MONITOR_MULTIPARAMETRO','OXIMETRO_WEARABLE','GLUCOMETRO_CGM','BOMBA_INFUSION')),
  modelo         VARCHAR(40) NOT NULL,
  frecuencia_seg INTEGER     NOT NULL CHECK (frecuencia_seg > 0)
);

CREATE TABLE asignacion_dispositivo (
  asignacion_id      BIGSERIAL   PRIMARY KEY,
  dispositivo_id     VARCHAR(12) NOT NULL REFERENCES dispositivo,
  hospitalizacion_id VARCHAR(16) NOT NULL REFERENCES hospitalizacion,
  desde              TIMESTAMPTZ NOT NULL,
  hasta              TIMESTAMPTZ,
  CHECK (hasta IS NULL OR hasta > desde)
);
CREATE UNIQUE INDEX ux_dispositivo_vigente ON asignacion_dispositivo (dispositivo_id) WHERE hasta IS NULL;
CREATE INDEX ix_asignacion_hosp ON asignacion_dispositivo (hospitalizacion_id);

-- ---------- Vista seudonimizada para analitica ----------
-- La analitica de telemetria no necesita nombre ni documento: solo edad,
-- sexo, territorio y episodio. Es lo unico que se cruza con MongoDB.
CREATE VIEW v_episodio_analitico AS
SELECT h.hospitalizacion_id, h.servicio, h.estado, h.dx_principal, h.fecha_admision, h.fecha_egreso,
       date_part('year', age(h.fecha_admision, p.fecha_nacimiento))::int AS edad,
       p.sexo, p.subregion, h.cama_id
FROM hospitalizacion h JOIN paciente p USING (paciente_id);

-- ---------- Tabla SOLO para la comparacion (misma ingesta que MongoDB) ----------
CREATE TABLE telemetria_jsonb (
  lectura_id     BIGSERIAL   PRIMARY KEY,
  dispositivo_id VARCHAR(12) NOT NULL,          -- sin FK a proposito: misma condicion que en MongoDB
  ts             TIMESTAMPTZ NOT NULL,
  tipo           VARCHAR(24) NOT NULL,
  lectura        JSONB       NOT NULL
);
CREATE INDEX ix_tel_disp_ts ON telemetria_jsonb (dispositivo_id, ts);
CREATE INDEX ix_tel_lectura ON telemetria_jsonb USING GIN (lectura jsonb_path_ops);
