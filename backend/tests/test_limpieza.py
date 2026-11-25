import pandas as pd
import pytest

from pipeline import COLUMNAS, MESES, NOMBRES, TIPOS_VISITANTE, limpiar_csv, preparar_entrada


def test_traduce_columnas_y_valores(csv_original):
    limpio, _ = limpiar_csv(csv_original)
    assert list(limpio.columns) == NOMBRES
    assert set(limpio['mes']) <= set(MESES)
    assert set(limpio['tipo_visitante']) <= set(TIPOS_VISITANTE)


def test_acepta_columnas_en_espanol(csv_original):
    en_espanol = csv_original.rename(columns=COLUMNAS)
    limpio, resumen = limpiar_csv(en_espanol)
    assert resumen['filas_validas'] == len(limpio) > 0


def test_elimina_duplicados(csv_original):
    con_duplicados = pd.concat([csv_original, csv_original.head(10)], ignore_index=True)
    _, resumen = limpiar_csv(con_duplicados)
    assert resumen['duplicados_eliminados'] >= 10


def test_descarta_filas_invalidas(csv_original):
    datos = csv_original.copy()
    datos.loc[0, 'BounceRates'] = 2
    datos.loc[1, 'Administrative'] = -1
    datos.loc[2, 'Month'] = 'Xyz'
    _, resumen = limpiar_csv(datos)
    assert resumen['filas_invalidas'] == 3


def test_imputa_nulos(csv_original):
    datos = csv_original.copy()
    datos.loc[0, 'PageValues'] = None
    limpio, resumen = limpiar_csv(datos)
    assert resumen['nulos_imputados'] >= 1
    assert limpio['valor_pagina'].notna().all()


def test_falta_una_columna(csv_original):
    with pytest.raises(ValueError, match='Faltan columnas'):
        limpiar_csv(csv_original.drop(columns='PageValues'))


def test_preparar_entrada_sin_objetivo(csv_original):
    limpio, _ = limpiar_csv(csv_original)
    X = preparar_entrada(limpio)
    assert 'compra' not in X.columns
    assert X['fin_de_semana'].isin([0, 1]).all()
