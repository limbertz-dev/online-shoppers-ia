"""Servicio de IA: API REST para predecir si una sesión de e-commerce termina en compra."""
import io
import json
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from db import engine
from pipeline import COLUMNAS, limpiar_csv, preparar_entrada
from schemas import (CargaRespuesta, HistorialRespuesta, ModeloMetricas, PrediccionRespuesta,
                     ReentrenamientoRespuesta, Salud, SesionEntrada)
from train import entrenar

BASE = Path(__file__).resolve().parent

app = FastAPI(
    title='Online Shoppers IA',
    version='1.0.0',
    description=(
        'Servicio de IA que predice si una sesión de navegación en una tienda online termina en **compra**.\n\n'
        'Modelo de clasificación supervisada entrenado con el dataset *Online Shoppers Purchasing Intention* '
        'siguiendo la metodología CRISP-ML(Q). Los datos de entrenamiento, los modelos con sus métricas y el '
        'historial de predicciones se guardan en PostgreSQL.\n\n'
        'Flujo: `POST /training-data` (subir CSV) → `POST /retrain` (entrenar) → `POST /predict` (predecir) → '
        '`GET /predictions` y `GET /metrics` (consultar).'
    ),
    openapi_tags=[
        {'name': 'Predicción', 'description': 'Enviar datos al modelo y consultar el historial.'},
        {'name': 'Modelo', 'description': 'Métricas de rendimiento y reentrenamiento.'},
        {'name': 'Datos', 'description': 'Carga del archivo de entrenamiento.'},
        {'name': 'Sistema', 'description': 'Estado del servicio.'},
    ],
)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

_cache_modelos = {}


def modelo_activo():
    """Devuelve (fila del modelo activo, pipeline cargado) o lanza 503 si no hay modelo."""
    with engine.connect() as con:
        fila = con.execute(text('SELECT id, version, umbral, ruta_archivo FROM modelo WHERE activo')).mappings().first()
    if not fila:
        raise HTTPException(503, 'No hay un modelo activo. Cargue datos con POST /training-data y ejecute POST /retrain.')
    if fila['id'] not in _cache_modelos:
        _cache_modelos[fila['id']] = joblib.load(BASE / fila['ruta_archivo'])
    return fila, _cache_modelos[fila['id']]


def fila_a_metricas(f) -> dict:
    return {
        'version': f['version'], 'algoritmo': f['algoritmo'], 'activo': f['activo'], 'umbral': float(f['umbral']),
        'metricas': {k: float(f[k]) for k in ['recall', 'precision', 'f1', 'f2', 'roc_auc']},
        'matriz_confusion': f['matriz_confusion'], 'hiperparametros': f['hiperparametros'],
        'filas_entrenamiento': f['filas_entrenamiento'], 'filas_prueba': f['filas_prueba'], 'fecha': f['fecha'],
    }


# ------------------------------------------------------------------ Predicción
@app.post('/predict', response_model=PrediccionRespuesta, tags=['Predicción'],
          summary='Enviar datos al modelo y obtener la predicción')
def predecir(sesion: SesionEntrada):
    """Recibe las 17 variables de una sesión, devuelve si habrá compra y la guarda en el historial."""
    fila, modelo = modelo_activo()
    entrada = sesion.model_dump()
    X = preparar_entrada(pd.DataFrame([entrada]))
    probabilidad = float(modelo.predict_proba(X)[0, 1])
    compra = probabilidad >= float(fila['umbral'])

    with engine.begin() as con:
        pid = con.execute(text('SELECT sp_registrar_prediccion(:m, CAST(:e AS JSONB), :r, :p)'),
                          {'m': fila['id'], 'e': json.dumps(entrada), 'r': compra, 'p': probabilidad}).scalar()
        fecha = con.execute(text('SELECT fecha FROM prediccion WHERE id = :id'), {'id': pid}).scalar()

    return {'id': pid, 'compra': compra, 'probabilidad': round(probabilidad, 4), 'umbral': float(fila['umbral']),
            'modelo_version': fila['version'], 'fecha': fecha}


@app.get('/predictions', response_model=HistorialRespuesta, tags=['Predicción'],
         summary='Historial de predicciones previas')
def historial(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    """Devuelve los datos enviados y el resultado de cada predicción, de la más reciente a la más antigua."""
    with engine.connect() as con:
        total = con.execute(text('SELECT COUNT(*) FROM prediccion')).scalar()
        filas = con.execute(text("""
            SELECT p.id, p.entrada, p.resultado AS compra, p.probabilidad, m.version AS modelo_version, p.fecha
            FROM prediccion p JOIN modelo m ON m.id = p.modelo_id
            ORDER BY p.fecha DESC, p.id DESC LIMIT :limit OFFSET :offset"""),
            {'limit': limit, 'offset': offset}).mappings().all()
    items = [{**f, 'probabilidad': float(f['probabilidad'])} for f in filas]
    return {'total': total, 'limit': limit, 'offset': offset, 'items': items}


# ------------------------------------------------------------------ Modelo
@app.get('/metrics', response_model=ModeloMetricas, tags=['Modelo'],
         summary='Métricas de rendimiento del modelo activo')
def metricas():
    """Recall, Precision, F1, F2, ROC-AUC y matriz de confusión del modelo activo (conjunto de prueba)."""
    with engine.connect() as con:
        f = con.execute(text('SELECT * FROM modelo WHERE activo')).mappings().first()
    if not f:
        raise HTTPException(404, 'No hay un modelo activo.')
    return fila_a_metricas(f)


@app.get('/metrics/history', response_model=list[ModeloMetricas], tags=['Modelo'],
         summary='Métricas de todas las versiones del modelo')
def metricas_historial():
    """Permite comparar cómo cambiaron las métricas en cada reentrenamiento."""
    with engine.connect() as con:
        filas = con.execute(text('SELECT * FROM modelo ORDER BY version DESC')).mappings().all()
    return [fila_a_metricas(f) for f in filas]


@app.post('/retrain', response_model=ReentrenamientoRespuesta, tags=['Modelo'],
          summary='Reentrenar el modelo con la información actualizada')
def reentrenar():
    """Entrena una nueva versión con todos los datos de la tabla de entrenamiento usando la configuración
    elegida en el notebook (algoritmo, hiperparámetros y criterio de umbral). Guarda sus métricas y la activa
    solo si cumple Recall >= 70 %."""
    try:
        return entrenar(engine)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ Datos
@app.post('/training-data', response_model=CargaRespuesta, tags=['Datos'],
          summary='Enviar el archivo CSV de entrenamiento')
async def cargar_datos(archivo: UploadFile = File(..., description='CSV con las 18 columnas del dataset'),
                       reemplazar: bool = Query(False, description='TRUE borra los datos anteriores antes de cargar')):
    """Valida y limpia el CSV (tipos, filas inválidas, nulos, duplicados) y lo guarda en la tabla de
    entrenamiento. Después se puede llamar a POST /retrain."""
    if not archivo.filename.lower().endswith('.csv'):
        raise HTTPException(400, 'El archivo debe ser .csv')
    contenido = await archivo.read()
    try:
        df = pd.read_csv(io.BytesIO(contenido))
        limpio, resumen = limpiar_csv(df)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f'No se pudo leer el CSV: {e}')
    if resumen['filas_validas'] == 0:
        raise HTTPException(400, 'El CSV no tiene filas válidas.')

    with engine.begin() as con:
        if reemplazar:
            con.execute(text('DELETE FROM dato_entrenamiento'))
        lote_id = con.execute(text("""
            INSERT INTO lote_carga (nombre_archivo, filas_recibidas, filas_validas, duplicados_eliminados, filas_invalidas)
            VALUES (:n, :r, :v, :d, :i) RETURNING id"""),
            {'n': archivo.filename, 'r': resumen['filas_recibidas'], 'v': resumen['filas_validas'],
             'd': resumen['duplicados_eliminados'], 'i': resumen['filas_invalidas']}).scalar()
        tabla = limpio.rename(columns=COLUMNAS)
        tabla['weekend'] = tabla['weekend'].astype(bool)
        tabla['revenue'] = tabla['revenue'].astype(bool)
        tabla.insert(0, 'lote_id', lote_id)
        tabla.to_sql('dato_entrenamiento', con, if_exists='append', index=False, method='multi', chunksize=1000)
        total = con.execute(text('SELECT COUNT(*) FROM dato_entrenamiento')).scalar()

    return {'lote_id': lote_id, 'nombre_archivo': archivo.filename, **resumen,
            'total_datos_entrenamiento': total, 'reemplazo': reemplazar}


# ------------------------------------------------------------------ Sistema
@app.get('/health', response_model=Salud, tags=['Sistema'], summary='Estado del servicio')
def salud():
    try:
        with engine.connect() as con:
            activo = con.execute(text('SELECT version FROM modelo WHERE activo')).scalar()
            datos = con.execute(text('SELECT COUNT(*) FROM dato_entrenamiento')).scalar()
        return {'api': 'ok', 'base_de_datos': 'ok', 'modelo_activo': activo, 'datos_entrenamiento': datos}
    except Exception:
        return {'api': 'ok', 'base_de_datos': 'sin conexión', 'modelo_activo': None, 'datos_entrenamiento': 0}


@app.get('/', include_in_schema=False)
def inicio():
    return RedirectResponse('/app/' if (BASE.parent / 'web' / 'index.html').exists() else '/docs')


# Cliente web servido por la misma API (opcional; también puede abrirse aparte)
if (BASE.parent / 'web').exists():
    app.mount('/app', StaticFiles(directory=BASE.parent / 'web', html=True), name='web')
