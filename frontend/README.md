# Frontend · Online Shoppers IA

Aplicación web (HTML + CSS + JavaScript) que consume el servicio de IA por API REST. Es un proyecto
independiente del backend: tiene su propio servidor y solo conoce la URL de la API (`config.js`).

## Ejecutar

```bash
cd frontend
python -m http.server 5500
```

Abrir http://localhost:5500 . El backend debe estar corriendo en la URL de `config.js`
(por defecto http://localhost:8000) y su variable `CORS_ORIGINS` debe incluir `http://localhost:5500`.

## Funciones

| Pestaña | Endpoint | Rol |
|---|---|---|
| Iniciar sesión | `POST /auth/login` (devuelve el JWT) | todos |
| Predecir | `POST /predict` | admin, analista |
| Historial | `GET /predictions` | admin, analista |
| Métricas | `GET /metrics`, `GET /metrics/history` | admin, analista |
| Datos de entrenamiento | `POST /training-data` | admin |
| Reentrenar | `POST /retrain` | admin |

El token se guarda en `sessionStorage` y se envía en cada petición como `Authorization: Bearer <token>`.
Si el backend responde 401 (token vencido o inválido) se vuelve a la pantalla de inicio de sesión.
