"""Exporta la descripción Swagger/OpenAPI de la API a docs/openapi.json.

Uso (desde la carpeta api):  python exportar_openapi.py
"""
import json
from pathlib import Path

from main import app

destino = Path(__file__).resolve().parent.parent / 'docs' / 'openapi.json'
destino.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding='utf-8')
print('Swagger exportado en', destino)
