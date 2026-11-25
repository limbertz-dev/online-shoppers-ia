import numpy as np
from sklearn.metrics import recall_score

from train import RECALL_MINIMO, elegir_umbral


def test_umbral_cumple_recall_minimo():
    rng = np.random.default_rng(42)
    y = rng.integers(0, 2, 500)
    prob = np.clip(y * 0.4 + rng.normal(0.3, 0.2, 500), 0, 1)
    umbral = elegir_umbral(y, prob)
    assert 0.10 <= umbral <= 0.90
    assert recall_score(y, prob >= umbral) >= RECALL_MINIMO


def test_umbral_con_separacion_perfecta():
    y = np.array([0] * 50 + [1] * 50)
    prob = np.array([0.1] * 50 + [0.9] * 50)
    umbral = elegir_umbral(y, prob)
    assert recall_score(y, prob >= umbral) == 1.0
