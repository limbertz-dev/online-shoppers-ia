-- =====================================================================
-- Online Shoppers IA - Script de generación de la base de datos
-- Motor: PostgreSQL 16
-- Uso:   psql -U postgres -c "CREATE DATABASE online_shoppers"
--        psql -U postgres -d online_shoppers -f db/schema.sql
--        (o abrir este archivo en DBeaver sobre la BD online_shoppers y ejecutarlo con Alt+X)
-- =====================================================================

DROP FUNCTION IF EXISTS sp_registrar_prediccion(INTEGER, JSONB, BOOLEAN, NUMERIC);
DROP FUNCTION IF EXISTS sp_activar_modelo(INTEGER);
DROP TABLE IF EXISTS prediccion;
DROP TABLE IF EXISTS modelo;
DROP TABLE IF EXISTS dato_entrenamiento;
DROP TABLE IF EXISTS lote_carga;
DROP TABLE IF EXISTS usuario;

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
--    (las 17 variables del dataset con nombres en español + la variable objetivo compra)
-- ---------------------------------------------------------------------
CREATE TABLE dato_entrenamiento (
    id                       SERIAL PRIMARY KEY,
    lote_id                  INTEGER       NOT NULL REFERENCES lote_carga(id) ON DELETE CASCADE,
    paginas_administrativas  INTEGER       NOT NULL CHECK (paginas_administrativas >= 0),
    tiempo_administrativas   NUMERIC(12,4) NOT NULL CHECK (tiempo_administrativas >= 0),
    paginas_informativas     INTEGER       NOT NULL CHECK (paginas_informativas >= 0),
    tiempo_informativas      NUMERIC(12,4) NOT NULL CHECK (tiempo_informativas >= 0),
    paginas_producto         INTEGER       NOT NULL CHECK (paginas_producto >= 0),
    tiempo_producto          NUMERIC(12,4) NOT NULL CHECK (tiempo_producto >= 0),
    tasa_rebote              NUMERIC(8,6)  NOT NULL CHECK (tasa_rebote BETWEEN 0 AND 1),
    tasa_salida              NUMERIC(8,6)  NOT NULL CHECK (tasa_salida BETWEEN 0 AND 1),
    valor_pagina             NUMERIC(12,6) NOT NULL CHECK (valor_pagina >= 0),
    dia_especial             NUMERIC(3,2)  NOT NULL CHECK (dia_especial BETWEEN 0 AND 1),
    mes                      VARCHAR(3)    NOT NULL CHECK (mes IN ('Ene','Feb','Mar','Abr','May','Jun',
                                                                   'Jul','Ago','Sep','Oct','Nov','Dic')),
    sistema_operativo        SMALLINT      NOT NULL,
    navegador                SMALLINT      NOT NULL,
    region                   SMALLINT      NOT NULL,
    tipo_trafico             SMALLINT      NOT NULL,
    tipo_visitante           VARCHAR(20)   NOT NULL CHECK (tipo_visitante IN ('Recurrente','Nuevo','Otro')),
    fin_de_semana            BOOLEAN       NOT NULL,
    compra                   BOOLEAN       NOT NULL,       -- variable objetivo
    fecha                    TIMESTAMP     NOT NULL DEFAULT NOW()
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
-- 5. usuario: cuentas para iniciar sesión (JWT) y su rol
--    password_hash = PBKDF2-SHA256 con sal (nunca la contraseña en texto plano)
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    id             SERIAL PRIMARY KEY,
    usuario        VARCHAR(50)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    rol            VARCHAR(20)  NOT NULL CHECK (rol IN ('admin', 'analista')),
    activo         BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Usuarios de demostración (contraseñas: admin123 y analista123)
INSERT INTO usuario (usuario, password_hash, rol) VALUES
('admin',    'pbkdf2_sha256$200000$fd8f33fbdc2b2fbb1e35b2e67eef45ca$61eca56837556988451418d146f25cafef72bf5a46bf6fe504735287e0c81fa7', 'admin'),
('analista', 'pbkdf2_sha256$200000$32b12c074f1f865bc40edf3bf9e7f2af$bc39cda4c4ee4e81b80509ebf19d2632ceb80dd63ffc3435eff8f69d42c892c2', 'analista');

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
