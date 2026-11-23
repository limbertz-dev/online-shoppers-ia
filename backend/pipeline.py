"""Limpieza de datos y construcción del pipeline del modelo.

Es el mismo procedimiento del notebook (notebooks/01_crispmlq_online_shoppers.ipynb):
- limpiar_csv(): validación y limpieza de un CSV antes de guardarlo en la BD.
- construir_pipeline(): preprocesamiento + algoritmo con los hiperparámetros elegidos.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'config_modelo.json').read_text(encoding='utf-8'))

# Nombre original del dataset (Kaggle, en inglés) -> nombre en español que usan la BD, la API y el modelo
COLUMNAS = {
    'Administrative': 'paginas_administrativas',
    'Administrative_Duration': 'tiempo_administrativas',
    'Informational': 'paginas_informativas',
    'Informational_Duration': 'tiempo_informativas',
    'ProductRelated': 'paginas_producto',
    'ProductRelated_Duration': 'tiempo_producto',
    'BounceRates': 'tasa_rebote',
    'ExitRates': 'tasa_salida',
    'PageValues': 'valor_pagina',
    'SpecialDay': 'dia_especial',
    'Month': 'mes',
    'OperatingSystems': 'sistema_operativo',
    'Browser': 'navegador',
    'Region': 'region',
    'TrafficType': 'tipo_trafico',
    'VisitorType': 'tipo_visitante',
    'Weekend': 'fin_de_semana',
    'Revenue': 'compra',
}
NOMBRES = list(COLUMNAS.values())
OBJETIVO = 'compra'
VARIABLES = [c for c in NOMBRES if c != OBJETIVO]
CATEGORICAS = CONFIG['columnas_categoricas']            # mes, tipo_visitante
NUMERICAS = CONFIG['columnas_numericas']                # resto (incluye fin_de_semana como 0/1)

MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
TIPOS_VISITANTE = ['Recurrente', 'Nuevo', 'Otro']
# Valores del CSV original que se traducen al español
TRADUCCION_MESES = {'Jan': 'Ene', 'Apr': 'Abr', 'June': 'Jun', 'Aug': 'Ago', 'Dec': 'Dic'}
TRADUCCION_VISITANTES = {'Returning_Visitor': 'Recurrente', 'New_Visitor': 'Nuevo', 'Other': 'Otro'}
PROPORCIONES = ['tasa_rebote', 'tasa_salida', 'dia_especial']   # deben estar entre 0 y 1


def a_booleano(serie: pd.Series) -> pd.Series:
    """Convierte TRUE/FALSE, true/false, 1/0 o bool a booleano (NaN si no se reconoce)."""
    mapa = {'true': True, 'false': False, '1': True, '0': False, '1.0': True, '0.0': False}
    return serie.astype(str).str.strip().str.lower().map(mapa)


def limpiar_csv(df: pd.DataFrame):
    """Valida y limpia un CSV de entrenamiento. Devuelve (df_limpio, resumen).
    Acepta el CSV original de Kaggle (columnas en inglés) o uno con las columnas en español."""
    df = df.rename(columns=COLUMNAS)
    faltantes = [c for c in NOMBRES if c not in df.columns]
    if faltantes:
        raise ValueError(f'Faltan columnas en el CSV: {faltantes}')

    df = df[NOMBRES].copy()
    recibidas = len(df)

    # Tipos y traducción de valores
    for c in NUMERICAS:
        if c != 'fin_de_semana':
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df['fin_de_semana'] = a_booleano(df['fin_de_semana'])
    df['compra'] = a_booleano(df['compra'])
    df['mes'] = df['mes'].astype(str).str.strip().replace(TRADUCCION_MESES)
    df['tipo_visitante'] = df['tipo_visitante'].astype(str).str.strip().replace(TRADUCCION_VISITANTES)

    # Filas inválidas: sin objetivo, valores negativos, proporciones fuera de [0,1] o categorías desconocidas
    invalida = df['compra'].isna()
    numericas_sin_fin = [c for c in NUMERICAS if c != 'fin_de_semana']
    invalida |= (df[numericas_sin_fin] < 0).any(axis=1)
    invalida |= (df[PROPORCIONES] > 1).any(axis=1)
    invalida |= ~df['mes'].isin(MESES + ['nan'])
    invalida |= ~df['tipo_visitante'].isin(TIPOS_VISITANTE + ['nan'])
    df = df[~invalida].copy()

    # Imputación de nulos en variables de entrada (mediana / moda), como en el pipeline del notebook
    nulos_imputados = int(df[VARIABLES].isna().sum().sum() + (df[CATEGORICAS] == 'nan').sum().sum())
    for c in numericas_sin_fin:
        df[c] = df[c].fillna(df[c].median())
    df['fin_de_semana'] = df['fin_de_semana'].fillna(
        df['fin_de_semana'].mode()[0] if df['fin_de_semana'].notna().any() else False)
    for c in CATEGORICAS:
        moda = df.loc[df[c] != 'nan', c].mode()
        df[c] = df[c].replace('nan', moda[0] if len(moda) else np.nan)

    # Duplicados
    antes = len(df)
    df = df.drop_duplicates()
    duplicados = antes - len(df)

    resumen = {
        'filas_recibidas': recibidas,
        'filas_invalidas': int(invalida.sum()),
        'nulos_imputados': nulos_imputados,
        'duplicados_eliminados': int(duplicados),
        'filas_validas': len(df),
    }
    return df.reset_index(drop=True), resumen


def preparar_entrada(df: pd.DataFrame) -> pd.DataFrame:
    """Deja las variables de entrada listas para el modelo (fin_de_semana como 0/1)."""
    X = df[VARIABLES].copy()
    X['fin_de_semana'] = X['fin_de_semana'].astype(int)
    return X


def construir_pipeline(peso_positivos: float) -> Pipeline:
    """Pipeline de preprocesamiento + algoritmo ganador del notebook con sus hiperparámetros."""
    preprocesador = ColumnTransformer([
        ('num', Pipeline([
            ('imputar', SimpleImputer(strategy='median')),
            ('escalar', StandardScaler()),
        ]), NUMERICAS),
        ('cat', Pipeline([
            ('imputar', SimpleImputer(strategy='most_frequent')),
            ('onehot', OneHotEncoder(handle_unknown='ignore')),
        ]), CATEGORICAS),
    ])

    rs = CONFIG['random_state']
    hp = CONFIG['hiperparametros']
    algoritmos = {
        'XGBoost': lambda: XGBClassifier(**hp, scale_pos_weight=peso_positivos, eval_metric='logloss',
                                         random_state=rs, n_jobs=-1),
        'Random Forest': lambda: RandomForestClassifier(**hp, class_weight='balanced', random_state=rs, n_jobs=-1),
        'Árbol de Decisión': lambda: DecisionTreeClassifier(**hp, class_weight='balanced', random_state=rs),
        'Regresión Logística': lambda: LogisticRegression(**hp, class_weight='balanced', max_iter=1000, random_state=rs),
        'KNN': lambda: KNeighborsClassifier(**hp),
    }
    return Pipeline([('prep', preprocesador), ('modelo', algoritmos[CONFIG['algoritmo']]())])
