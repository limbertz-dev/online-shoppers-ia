"""Autenticación con JSON Web Token (JWT) y autorización por roles.

- Las contraseñas se guardan como hash PBKDF2-SHA256 con sal (nunca en texto plano).
- POST /auth/login valida usuario y contraseña y devuelve un JWT firmado (HS256) con vencimiento.
- Los endpoints protegidos exigen el encabezado  Authorization: Bearer <token>.
- Roles: 'admin' (todo) y 'analista' (predecir y consultar).
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text

from db import engine

JWT_SECRET = os.getenv('JWT_SECRET', 'cambiar-esta-clave-en-produccion')
JWT_ALGORITMO = 'HS256'
JWT_MINUTOS = int(os.getenv('JWT_MINUTOS', '60'))

oauth2 = OAuth2PasswordBearer(tokenUrl='/auth/login')


def verificar_password(password: str, guardado: str) -> bool:
    """Compara la contraseña con el hash guardado: pbkdf2_sha256$iteraciones$sal$hash."""
    try:
        _, iteraciones, sal, esperado = guardado.split('$')
        calculado = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(sal), int(iteraciones)).hex()
        return hmac.compare_digest(calculado, esperado)
    except ValueError:
        return False


def autenticar(usuario: str, password: str):
    with engine.connect() as con:
        fila = con.execute(text('SELECT id, usuario, password_hash, rol FROM usuario WHERE usuario = :u AND activo'),
                           {'u': usuario}).mappings().first()
    if not fila or not verificar_password(password, fila['password_hash']):
        return None
    return fila


def crear_token(usuario: str, rol: str) -> str:
    ahora = datetime.now(timezone.utc)
    datos = {'sub': usuario, 'rol': rol, 'iat': ahora, 'exp': ahora + timedelta(minutes=JWT_MINUTOS)}
    return jwt.encode(datos, JWT_SECRET, algorithm=JWT_ALGORITMO)


def usuario_actual(token: str = Depends(oauth2)) -> dict:
    """Dependencia: valida el JWT y devuelve {'usuario', 'rol'}; si no es válido responde 401."""
    try:
        datos = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITMO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'El token venció; inicie sesión de nuevo.',
                            headers={'WWW-Authenticate': 'Bearer'})
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Token inválido.', headers={'WWW-Authenticate': 'Bearer'})
    return {'usuario': datos['sub'], 'rol': datos['rol']}


def solo_admin(actual: dict = Depends(usuario_actual)) -> dict:
    """Dependencia: además de un token válido, exige el rol 'admin' (403 si no lo tiene)."""
    if actual['rol'] != 'admin':
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Esta acción requiere el rol admin.')
    return actual
