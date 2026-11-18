# Online Shoppers IA

Solución de inteligencia artificial que predice si una sesión de navegación en una tienda online **termina en compra**. Incluye:

- El entrenamiento del modelo siguiendo **CRISP-ML(Q)**, en un notebook de Jupyter.
- Un **backend**: servicio de IA con FastAPI, API REST protegida con **JWT** y documentada con Swagger.
- Una base de datos **PostgreSQL**.
- Un **frontend** independiente que consume todos los endpoints.

Trabajo final · SIS-352

## Arquitectura

```
Jupyter (EDA + pruebas) ──config_modelo.json──► backend/  Servicio de IA (FastAPI, puerto 8000)
                                                  ▲   │
                         API REST + JWT (Bearer)  │   ▼
                         CORS: solo el frontend   │   PostgreSQL: usuario · lote_carga ·
                                                  │   dato_entrenamiento · modelo · prediccion
frontend/  Aplicación web (puerto 5500) ──────────┘
```

**Backend y frontend son dos proyectos independientes:** cada uno tiene su propio servidor y se comunican solo por la API REST.

1. El usuario inicia sesión → `POST /auth/login` devuelve un JWT, que viaja en cada petición como `Authorization: Bearer <token>`.
2. El admin sube un CSV → el backend lo valida y limpia (tipos, filas inválidas, nulos, duplicados) y lo guarda en `dato_entrenamiento`.
3. `POST /retrain` entrena una nueva versión con los datos de la BD, usando el algoritmo, los hiperparámetros y el umbral elegidos en el notebook, y guarda sus métricas en `modelo`.
4. `POST /predict` usa el modelo activo y guarda la entrada y el resultado en `prediccion`.

## Dataset y modelo

- **Dataset:** [Online Shoppers Purchasing Intention](https://www.kaggle.com/datasets/imakash3011/online-shoppers-purchasing-intention-dataset): 12 330 sesiones, 17 variables, objetivo `Revenue` (15,5 % compras).
- **Problema:** clasificación binaria supervisada.
- **Métrica:** Recall(compra) ≥ 70 % como requisito, F2 como métrica principal y ROC-AUC de apoyo.
- **Modelos comparados:** Regresión Logística, Árbol de Decisión, KNN, Random Forest y XGBoost.
- **Modelo elegido:** XGBoost, con umbral 0,44.

| Recall (compra) | Precision | F1 | F2 | ROC-AUC |
|---|---|---|---|---|
| 0,893 | 0,506 | 0,646 | 0,774 | 0,939 |

## Cómo ejecutarlo

Requisitos: Docker Desktop y Python 3.13.

```bash
# 0. Configuración
copy .env.example .env             # Linux/Mac: cp .env.example .env  (cambie JWT_SECRET)

# 1. Base de datos (crea tablas, procedimientos y usuarios demo con db/schema.sql)
docker compose up -d

# 2. Backend: servicio de IA
python -m venv .venv
.venv\Scripts\activate             # Linux/Mac: source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --port 8000

# 3. Frontend (en otra terminal)
cd frontend
python -m http.server 5500
```

- Frontend: http://localhost:5500
- Swagger del backend: http://localhost:8000/docs (botón **Authorize** para usar el token)

**Usuarios de demostración:**

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin123` | Todo |
| `analista` | `analista123` | Predecir y consultar |

**Primer uso:** inicie sesión como `admin`, suba `data/online_shoppers_intention.csv` en **Datos de entrenamiento** y pulse **Reentrenar**. Con eso ya se puede predecir.

**Notebook:** `pip install -r requirements-notebook.txt` y abrir `notebooks/01_crispmlq_online_shoppers.ipynb`.

## Endpoints

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| POST | `/auth/login` | Iniciar sesión y obtener el JWT | público |
| GET | `/auth/me` | Usuario del token | token |
| POST | `/predict` | Enviar datos de una sesión y obtener la predicción | token |
| GET | `/predictions` | Historial de predicciones (datos enviados + resultado) | token |
| GET | `/metrics` | Métricas del modelo activo | token |
| GET | `/metrics/history` | Métricas de todas las versiones | token |
| POST | `/retrain` | Reentrenar con la información actualizada | admin |
| POST | `/training-data` | Enviar el archivo CSV de entrenamiento | admin |
| GET | `/health` | Estado del servicio | público |

Documento Swagger exportado: [`docs/openapi.json`](docs/openapi.json). Se regenera con `python backend/exportar_openapi.py`.

## Seguridad

- **JWT (HS256):** se firma con `JWT_SECRET` y vence a los `JWT_MINUTOS`. Sin token o con un token inválido o vencido, la API responde **401**.
- **Autorización por rol:** `/retrain` y `/training-data` exigen el rol `admin`; si no lo tiene, la API responde **403**.
- **Contraseñas:** se guardan como hash PBKDF2-SHA256 con sal, en la tabla `usuario`.
- **CORS:** solo los orígenes listados en `CORS_ORIGINS` (`.env`) pueden consumir la API desde el navegador.
- Los secretos van en `.env`, que no se sube al repositorio. En el repositorio solo está `.env.example`.

## Estructura

```
notebooks/   Notebook CRISP-ML(Q): EDA, preparación, comparación de modelos, evaluación
data/        Dataset original
backend/     Servicio de IA (main, auth, pipeline, train, schemas, db) y configuración del modelo
frontend/    Aplicación web independiente (HTML, CSS, JavaScript, config.js)
db/          schema.sql (script de generación) y diagrama de la base de datos
docs/        Documento CRISP-ML(Q) (PDF), Swagger (openapi.json) y capturas
```

## Ramas

| Rama | Contenido |
|---|---|
| `main` | Versión entregada |
| `develop` | Integración |
| `feature/ciencia-datos` | Notebook y modelo |
| `feature/api` | Backend: servicio de IA |
| `feature/frontend` | Aplicación web |

Cada característica se integró a `develop` mediante un pull request, y `develop` se integró a `main` de la misma forma.

## Base de datos

![Diagrama de base de datos](db/diagrama_bd.png)

Script de generación: [`db/schema.sql`](db/schema.sql).
