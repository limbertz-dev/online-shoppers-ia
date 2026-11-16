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

# Nombre en el CSV -> nombre de columna en la BD
COLUMNAS = {
    'Administrative': 'administrative',
    'Administrative_Duration': 'administrative_duration',
    'Informational': 'informational',
    'Informational_Duration': 'informational_duration',
    'ProductRelated': 'product_related',
    'ProductRelated_Duration': 'product_related_duration',
    'BounceRates': 'bounce_rates',
    'ExitRates': 'exit_rates',
    'PageValues': 'page_values',
    'SpecialDay': 'special_day',
    'Month': 'month',
    'OperatingSystems': 'operating_systems',
    'Browser': 'browser',
    'Region': 'region',
    'TrafficType': 'traffic_type',
    'VisitorType': 'visitor_type',
    'Weekend': 'weekend',
    'Revenue': 'revenue',
}
VARIABLES = [c for c in COLUMNAS if c != 'Revenue']
OBJETIVO = 'Revenue'
CATEGORICAS = CONFIG['columnas_categoricas']            # Month, VisitorType
NUMERICAS = CONFIG['columnas_numericas']                # resto (incluye Weekend como 0/1)

MESES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
TIPOS_VISITANTE = ['Returning_Visitor', 'New_Visitor', 'Other']
PROPORCIONES = ['BounceRates', 'ExitRates', 'SpecialDay']   # deben estar entre 0 y 1


def a_booleano(serie: pd.Series) -> pd.Series:
    """Convierte TRUE/FALSE, true/false, 1/0 o bool a booleano (NaN si no se reconoce)."""
    mapa = {'true': True, 'false': False, '1': True, '0': False, '1.0': True, '0.0': False}
    return serie.astype(str).str.strip().str.lower().map(mapa)


def limpiar_csv(df: pd.DataFrame):
    """Valida y limpia un CSV de entrenamiento. Devuelve (df_limpio, resumen)."""
    faltantes = [c for c in COLUMNAS if c not in df.columns]
    if faltantes:
        raise ValueError(f'Faltan columnas en el CSV: {faltantes}')

    df = df[list(COLUMNAS)].copy()
    recibidas = len(df)

    # Tipos
    for c in NUMERICAS:
        if c != 'Weekend':
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df['Weekend'] = a_booleano(df['Weekend'])
    df['Revenue'] = a_booleano(df['Revenue'])
    df['Month'] = df['Month'].astype(str).str.strip()
    df['VisitorType'] = df['VisitorType'].astype(str).str.strip()

    # Filas inválidas: sin objetivo, valores negativos, proporciones fuera de [0,1] o categorías desconocidas
    invalida = df['Revenue'].isna()
    numericas_sin_weekend = [c for c in NUMERICAS if c != 'Weekend']
    invalida |= (df[numericas_sin_weekend] < 0).any(axis=1)
    invalida |= (df[PROPORCIONES] > 1).any(axis=1)
    invalida |= ~df['Month'].isin(MESES + ['nan'])
    invalida |= ~df['VisitorType'].isin(TIPOS_VISITANTE + ['nan'])
    df = df[~invalida].copy()

    # Imputación de nulos en variables de entrada (mediana / moda), como en el pipeline del notebook
    nulos_imputados = int(df[VARIABLES].isna().sum().sum() + (df[CATEGORICAS] == 'nan').sum().sum())
    for c in numericas_sin_weekend:
        df[c] = df[c].fillna(df[c].median())
    df['Weekend'] = df['Weekend'].fillna(df['Weekend'].mode()[0] if df['Weekend'].notna().any() else False)
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
    """Deja las variables de entrada listas para el modelo (Weekend como 0/1)."""
    X = df[VARIABLES].copy()
    X['Weekend'] = X['Weekend'].astype(int)
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
