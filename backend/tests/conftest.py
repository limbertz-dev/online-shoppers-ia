import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DATOS = BACKEND.parent / 'data' / 'online_shoppers_intention_mini.csv'


@pytest.fixture
def csv_original():
    return pd.read_csv(DATOS).head(200).reset_index(drop=True)
