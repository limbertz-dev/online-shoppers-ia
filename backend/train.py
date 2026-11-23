"""Entrenamiento / reentrenamiento del modelo con los datos guardados en la BD."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (confusion_matrix, f1_score, fbeta_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sqlalchemy import text

from pipeline import CONFIG, NOMBRES, OBJETIVO, construir_pipeline, preparar_entrada

BASE = Path(__file__).resolve().parent
RECALL_MINIMO = 0.70


def elegir_umbral(y, prob):
    """Umbral que maximiza F2 cumpliendo Recall >= 70 % (mismo criterio del notebook)."""
    mejor_umbral, mejor_f2 = 0.5, -1
    for u in np.arange(0.10, 0.91, 0.01):
        pred = prob >= u
        if recall_score(y, pred) >= RECALL_MINIMO:
            f2 = fbeta_score(y, pred, beta=2)
            if f2 > mejor_f2:
                mejor_umbral, mejor_f2 = round(float(u), 2), f2
    return mejor_umbral


def entrenar(engine) -> dict:
    """Lee dato_entrenamiento, entrena, evalúa, guarda el modelo y sus métricas en la BD."""
    df = pd.read_sql('SELECT * FROM dato_entrenamiento ORDER BY id', engine)
    # Quita duplicados entre lotes (un mismo registro subido dos veces no debe contar doble
    # ni quedar a la vez en entrenamiento y prueba)
    df = df.drop_duplicates(subset=NOMBRES).reset_index(drop=True)
    if len(df) < 100:
        raise ValueError(f'Hay solo {len(df)} filas de entrenamiento; se necesitan al menos 100.')

    X = preparar_entrada(df)
    y = df[OBJETIVO].astype(int)
    if y.nunique() < 2 or y.value_counts().min() < 10:
        raise ValueError('Se necesitan ejemplos de ambas clases (al menos 10 por clase).')

    rs = CONFIG['random_state']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=rs)
    peso = float((y_train == 0).sum() / (y_train == 1).sum())
    modelo = construir_pipeline(peso)

    # Umbral con validación cruzada sobre el entrenamiento (sin tocar el test)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=rs)
    prob_cv = cross_val_predict(modelo, X_train, y_train, cv=cv, method='predict_proba')[:, 1]
    umbral = elegir_umbral(y_train, prob_cv)

    modelo.fit(X_train, y_train)
    prob = modelo.predict_proba(X_test)[:, 1]
    pred = (prob >= umbral).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()
    metricas = {
        'recall': recall_score(y_test, pred),
        'precision': precision_score(y_test, pred, zero_division=0),
        'f1': f1_score(y_test, pred),
        'f2': fbeta_score(y_test, pred, beta=2),
        'roc_auc': roc_auc_score(y_test, prob),
    }
    metricas = {k: round(float(v), 4) for k, v in metricas.items()}

    with engine.begin() as con:
        anterior = con.execute(text('SELECT version, recall, precision, f1, f2, roc_auc '
                                    'FROM modelo WHERE activo')).mappings().first()
        version = con.execute(text('SELECT COALESCE(MAX(version), 0) + 1 FROM modelo')).scalar()
        ruta = f'models/modelo_v{version}.joblib'
        joblib.dump(modelo, BASE / ruta)

        nuevo_id = con.execute(text("""
            INSERT INTO modelo (version, algoritmo, hiperparametros, umbral, recall, precision, f1, f2, roc_auc,
                                matriz_confusion, filas_entrenamiento, filas_prueba, ruta_archivo)
            VALUES (:version, :algoritmo, CAST(:hp AS JSONB), :umbral, :recall, :precision, :f1, :f2, :roc_auc,
                    CAST(:mc AS JSONB), :n_train, :n_test, :ruta)
            RETURNING id"""), {
            'version': version, 'algoritmo': CONFIG['algoritmo'],
            'hp': json.dumps({**CONFIG['hiperparametros'], **({'scale_pos_weight': round(peso, 4)}
                                                               if CONFIG['algoritmo'] == 'XGBoost' else {})}),
            'umbral': umbral, **metricas,
            'mc': json.dumps({'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)}),
            'n_train': len(X_train), 'n_test': len(X_test), 'ruta': ruta,
        }).scalar()

        # Se activa solo si cumple el requisito de negocio (Recall >= 70 %)
        activado = metricas['recall'] >= RECALL_MINIMO
        if activado:
            con.execute(text('SELECT sp_activar_modelo(:id)'), {'id': nuevo_id})

    return {
        'modelo_id': nuevo_id,
        'version': version,
        'algoritmo': CONFIG['algoritmo'],
        'activado': activado,
        'motivo': ('Cumple Recall >= 70 %; es el nuevo modelo activo.' if activado else
                   'No cumple Recall >= 70 %; se mantiene el modelo anterior.'),
        'umbral': umbral,
        'metricas': metricas,
        'matriz_confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
        'filas_entrenamiento': len(X_train),
        'filas_prueba': len(X_test),
        'modelo_anterior': ({k: (float(v) if k != 'version' else v) for k, v in anterior.items()}
                            if anterior else None),
    }
