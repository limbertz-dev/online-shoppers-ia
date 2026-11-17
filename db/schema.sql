-- =====================================================================
-- Online Shoppers IA - Script de generación de la base de datos
-- Motor: PostgreSQL 16
-- Uso:   psql -U postgres -d online_shoppers -f db/schema.sql
--        (con Docker se ejecuta solo al crear el contenedor)
-- =====================================================================

DROP FUNCTION IF EXISTS sp_registrar_prediccion(INTEGER, JSONB, BOOLEAN, NUMERIC);
DROP FUNCTION IF EXISTS sp_activar_modelo(INTEGER);
DROP TABLE IF EXISTS prediccion;
DROP TABLE IF EXISTS modelo;
DROP TABLE IF EXISTS dato_entrenamiento;
DROP TABLE IF EXISTS lote_carga;

-- ---------------------------------------------------------------------
-- 1. lote_carga: cada archivo CSV enviado al servicio
-- ---------------------------------------------------------------------
CREATE TABLE lote_carga (
    id                     SERIAL PRIMARY KEY,
    nombre_archivo         VARCHAR(255) NOT NULL,
    filas_recibidas        INTEGER      NOT NULL,
    filas_validas          INTEGER      NOT NULL,
    duplicados_eliminados  INTEGER      NOT NULL DEFAULT 0,
    filas_invalidas        INTEGER      NOT NULL DEFAULT 0,
    fecha                  TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
-- 2. dato_entrenamiento: datos limpios con los que se entrena el modelo
--    (mismas 17 variables del CSV + la variable objetivo revenue)
-- ---------------------------------------------------------------------
CREATE TABLE dato_entrenamiento (
    id                        SERIAL PRIMARY KEY,
    lote_id                   INTEGER      NOT NULL REFERENCES lote_carga(id) ON DELETE CASCADE,
    administrative            INTEGER      NOT NULL CHECK (administrative >= 0),
    administrative_duration   NUMERIC(12,4) NOT NULL CHECK (administrative_duration >= 0),
    informational             INTEGER      NOT NULL CHECK (informational >= 0),
    informational_duration    NUMERIC(12,4) NOT NULL CHECK (informational_duration >= 0),
    product_related           INTEGER      NOT NULL CHECK (product_related >= 0),
    product_related_duration  NUMERIC(12,4) NOT NULL CHECK (product_related_duration >= 0),
    bounce_rates              NUMERIC(8,6) NOT NULL CHECK (bounce_rates BETWEEN 0 AND 1),
    exit_rates                NUMERIC(8,6) NOT NULL CHECK (exit_rates BETWEEN 0 AND 1),
    page_values               NUMERIC(12,6) NOT NULL CHECK (page_values >= 0),
    special_day               NUMERIC(3,2) NOT NULL CHECK (special_day BETWEEN 0 AND 1),
    month                     VARCHAR(4)   NOT NULL,
    operating_systems         SMALLINT     NOT NULL,
    browser                   SMALLINT     NOT NULL,
    region                    SMALLINT     NOT NULL,
    traffic_type              SMALLINT     NOT NULL,
    visitor_type              VARCHAR(20)  NOT NULL,
    weekend                   BOOLEAN      NOT NULL,
    revenue                   BOOLEAN      NOT NULL,
    fecha                     TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_dato_entrenamiento_lote ON dato_entrenamiento(lote_id);

-- ---------------------------------------------------------------------
-- 3. modelo: cada entrenamiento / reentrenamiento y sus métricas
-- ---------------------------------------------------------------------
CREATE TABLE modelo (
    id                   SERIAL PRIMARY KEY,
    version              INTEGER      NOT NULL UNIQUE,
    algoritmo            VARCHAR(50)  NOT NULL,
    hiperparametros      JSONB        NOT NULL,
    umbral               NUMERIC(4,2) NOT NULL,
    recall               NUMERIC(6,4) NOT NULL,
    precision            NUMERIC(6,4) NOT NULL,
    f1                   NUMERIC(6,4) NOT NULL,
    f2                   NUMERIC(6,4) NOT NULL,
    roc_auc              NUMERIC(6,4) NOT NULL,
    matriz_confusion     JSONB        NOT NULL,   -- {"tn":..,"fp":..,"fn":..,"tp":..}
    filas_entrenamiento  INTEGER      NOT NULL,
    filas_prueba         INTEGER      NOT NULL,
    ruta_archivo         VARCHAR(255) NOT NULL,
    activo               BOOLEAN      NOT NULL DEFAULT FALSE,
    fecha                TIMESTAMP    NOT NULL DEFAULT NOW()
);
-- Solo puede haber un modelo activo a la vez
CREATE UNIQUE INDEX ux_modelo_un_activo ON modelo(activo) WHERE activo;

-- ---------------------------------------------------------------------
-- 4. prediccion: historial de predicciones (datos enviados + resultado)
-- ---------------------------------------------------------------------
CREATE TABLE prediccion (
    id            SERIAL PRIMARY KEY,
    modelo_id     INTEGER      NOT NULL REFERENCES modelo(id),
    entrada       JSONB        NOT NULL,
    resultado     BOOLEAN      NOT NULL,       -- TRUE = compra
    probabilidad  NUMERIC(6,4) NOT NULL CHECK (probabilidad BETWEEN 0 AND 1),
    fecha         TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_prediccion_fecha ON prediccion(fecha DESC);

-- ---------------------------------------------------------------------
-- Procedimiento: registrar una predicción y devolver su id
-- ---------------------------------------------------------------------
CREATE FUNCTION sp_registrar_prediccion(
    p_modelo_id    INTEGER,
    p_entrada      JSONB,
    p_resultado    BOOLEAN,
    p_probabilidad NUMERIC
) RETURNS INTEGER
LANGUAGE plpgsql AS $$
DECLARE
    v_id INTEGER;
BEGIN
    INSERT INTO prediccion (modelo_id, entrada, resultado, probabilidad)
    VALUES (p_modelo_id, p_entrada, p_resultado, ROUND(p_probabilidad, 4))
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

-- ---------------------------------------------------------------------
-- Procedimiento: activar un modelo (desactiva el anterior)
-- ---------------------------------------------------------------------
CREATE FUNCTION sp_activar_modelo(p_modelo_id INTEGER) RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE modelo SET activo = FALSE WHERE activo;
    UPDATE modelo SET activo = TRUE  WHERE id = p_modelo_id;
END;
$$;
