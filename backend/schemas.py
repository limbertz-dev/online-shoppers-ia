"""Esquemas Pydantic: validan la entrada y documentan las respuestas en Swagger."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Mes = Literal['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
TipoVisitante = Literal['Recurrente', 'Nuevo', 'Otro']


class SesionEntrada(BaseModel):
    """Datos de una sesión de navegación (las 17 variables del dataset, con nombres en español)."""
    paginas_administrativas: int = Field(ge=0, description='Páginas administrativas visitadas (Administrative)')
    tiempo_administrativas: float = Field(ge=0, description='Segundos en páginas administrativas')
    paginas_informativas: int = Field(ge=0, description='Páginas informativas visitadas (Informational)')
    tiempo_informativas: float = Field(ge=0, description='Segundos en páginas informativas')
    paginas_producto: int = Field(ge=0, description='Páginas de productos visitadas (ProductRelated)')
    tiempo_producto: float = Field(ge=0, description='Segundos en páginas de productos')
    tasa_rebote: float = Field(ge=0, le=1, description='Tasa de rebote promedio de las páginas visitadas (BounceRates)')
    tasa_salida: float = Field(ge=0, le=1, description='Tasa de salida promedio de las páginas visitadas (ExitRates)')
    valor_pagina: float = Field(ge=0, description='Valor promedio de las páginas visitadas antes de comprar (PageValues)')
    dia_especial: float = Field(ge=0, le=1, description='Cercanía a una fecha especial, 0 a 1 (SpecialDay)')
    mes: Mes = Field(description='Mes de la sesión')
    sistema_operativo: int = Field(ge=1, description='Código del sistema operativo')
    navegador: int = Field(ge=1, description='Código del navegador')
    region: int = Field(ge=1, description='Código de la región')
    tipo_trafico: int = Field(ge=1, description='Código del tipo de tráfico')
    tipo_visitante: TipoVisitante = Field(description='Tipo de visitante')
    fin_de_semana: bool = Field(description='La sesión fue en fin de semana')

    model_config = ConfigDict(json_schema_extra={'example': {
        'paginas_administrativas': 3, 'tiempo_administrativas': 85.0, 'paginas_informativas': 0,
        'tiempo_informativas': 0.0, 'paginas_producto': 40, 'tiempo_producto': 1500.0,
        'tasa_rebote': 0.005, 'tasa_salida': 0.02, 'valor_pagina': 25.5, 'dia_especial': 0.0,
        'mes': 'Nov', 'sistema_operativo': 2, 'navegador': 2, 'region': 1, 'tipo_trafico': 2,
        'tipo_visitante': 'Recurrente', 'fin_de_semana': False}})


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


class Token(BaseModel):
    access_token: str = Field(description='JSON Web Token; enviarlo como  Authorization: Bearer <token>')
    token_type: str = 'bearer'
    expira_en_minutos: int
    usuario: str
    rol: str


class UsuarioActual(BaseModel):
    usuario: str
    rol: str
