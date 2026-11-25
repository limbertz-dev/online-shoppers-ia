from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from auth import JWT_ALGORITMO, JWT_SECRET, crear_token
from main import ORIGENES, app


@pytest.fixture
def cliente():
    return TestClient(app)


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def test_sin_token_responde_401(cliente):
    assert cliente.get('/metrics').status_code == 401
    assert cliente.get('/predictions').status_code == 401


def test_token_falso_responde_401(cliente):
    r = cliente.get('/auth/me', headers=bearer('token.falso.x'))
    assert r.status_code == 401


def test_token_con_otra_firma_responde_401(cliente):
    futuro = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = jwt.encode({'sub': 'admin', 'rol': 'admin', 'exp': futuro}, 'otra-clave-distinta', algorithm=JWT_ALGORITMO)
    assert cliente.get('/auth/me', headers=bearer(token)).status_code == 401


def test_token_vencido_responde_401(cliente):
    pasado = datetime.now(timezone.utc) - timedelta(minutes=5)
    token = jwt.encode({'sub': 'admin', 'rol': 'admin', 'exp': pasado}, JWT_SECRET, algorithm=JWT_ALGORITMO)
    r = cliente.get('/auth/me', headers=bearer(token))
    assert r.status_code == 401
    assert 'venció' in r.json()['detail']


def test_token_valido_devuelve_usuario(cliente):
    r = cliente.get('/auth/me', headers=bearer(crear_token('analista', 'analista')))
    assert r.status_code == 200
    assert r.json() == {'usuario': 'analista', 'rol': 'analista'}


def test_analista_no_puede_reentrenar_ni_subir(cliente):
    token = bearer(crear_token('analista', 'analista'))
    assert cliente.post('/retrain', headers=token).status_code == 403
    assert cliente.post('/training-data', headers=token).status_code == 403


def test_cors_solo_frontend(cliente):
    preflight = {'Access-Control-Request-Method': 'POST'}
    ok = cliente.options('/predict', headers={**preflight, 'Origin': ORIGENES[0]})
    otro = cliente.options('/predict', headers={**preflight, 'Origin': 'http://otro-sitio.com'})
    assert ok.status_code == 200
    assert otro.status_code == 400
