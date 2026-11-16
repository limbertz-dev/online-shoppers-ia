"""Esquemas Pydantic: validan la entrada y documentan las respuestas en Swagger."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Mes = Literal['Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
TipoVisitante = Literal['Returning_Visitor', 'New_Visitor', 'Other']


class SesionEntrada(BaseModel):
    """Datos de una sesión de navegación (las 17 variables del dataset)."""
    Administrative: int = Field(ge=0, description='Páginas administrativas visitadas')
    Administrative_Duration: float = Field(ge=0, description='Segundos en páginas administrativas')
    Informational: int = Field(ge=0, description='Páginas informativas visitadas')
    Informational_Duration: float = Field(ge=0, description='Segundos en páginas informativas')
    ProductRelated: int = Field(ge=0, description='Páginas de productos visitadas')
    ProductRelated_Duration: float = Field(ge=0, description='Segundos en páginas de productos')
    BounceRates: float = Field(ge=0, le=1, description='Tasa de rebote promedio de las páginas visitadas')
    ExitRates: float = Field(ge=0, le=1, description='Tasa de salida promedio de las páginas visitadas')
    PageValues: float = Field(ge=0, description='Valor promedio de las páginas visitadas antes de comprar')
    SpecialDay: float = Field(ge=0, le=1, description='Cercanía a una fecha especial (0 a 1)')
    Month: Mes = Field(description='Mes de la sesión')
    OperatingSystems: int = Field(ge=1, description='Código del sistema operativo')
    Browser: int = Field(ge=1, description='Código del navegador')
    Region: int = Field(ge=1, description='Código de la región')
    TrafficType: int = Field(ge=1, description='Código del tipo de tráfico')
    VisitorType: TipoVisitante = Field(description='Tipo de visitante')
    Weekend: bool = Field(description='La sesión fue en fin de semana')

    model_config = ConfigDict(json_schema_extra={'example': {
        'Administrative': 3, 'Administrative_Duration': 85.0, 'Informational': 0,
        'Informational_Duration': 0.0, 'ProductRelated': 40, 'ProductRelated_Duration': 1500.0,
        'BounceRates': 0.005, 'ExitRates': 0.02, 'PageValues': 25.5, 'SpecialDay': 0.0,
        'Month': 'Nov', 'OperatingSystems': 2, 'Browser': 2, 'Region': 1, 'TrafficType': 2,
        'VisitorType': 'Returning_Visitor', 'Weekend': False}})


class PrediccionRespuesta(BaseModel):
    id: int = Field(description='Id de la predicción guardada en el historial')
    compra: bool = Field(description='TRUE si el modelo predice que la sesión termina en compra')
    probabilidad: float = Field(description='Probabilidad de compra estimada por el modelo')
    umbral: float = Field(description='Umbral de decisión del modelo activo')
    modelo_version: int
    fecha: datetime


class PrediccionHistorial(BaseModel):
    id: int
    entrada: dict
    compra: bool
    probabilidad: float
    modelo_version: int
    fecha: datetime


class HistorialRespuesta(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PrediccionHistorial]


class Metricas(BaseModel):
    recall: float
    precision: float
    f1: float
    f2: float
    roc_auc: float


class ModeloMetricas(BaseModel):
    version: int
    algoritmo: str
    activo: bool
    umbral: float
    metricas: Metricas
    matriz_confusion: dict = Field(description='{"tn", "fp", "fn", "tp"} sobre el conjunto de prueba')
    hiperparametros: dict
    filas_entrenamiento: int
    filas_prueba: int
    fecha: datetime


class ReentrenamientoRespuesta(BaseModel):
    modelo_id: int
    version: int
    algoritmo: str
    activado: bool
    motivo: str
    umbral: float
    metricas: Metricas
    matriz_confusion: dict
    filas_entrenamiento: int
    filas_prueba: int
    modelo_anterior: Optional[dict] = Field(description='Métricas del modelo que estaba activo antes')


class CargaRespuesta(BaseModel):
    lote_id: int
    nombre_archivo: str
    filas_recibidas: int
    filas_invalidas: int
    nulos_imputados: int
    duplicados_eliminados: int
    filas_validas: int
    total_datos_entrenamiento: int = Field(description='Filas totales en la tabla de entrenamiento tras la carga')
    reemplazo: bool


class Salud(BaseModel):
    api: str
    base_de_datos: str
    modelo_activo: Optional[int]
    datos_entrenamiento: int
