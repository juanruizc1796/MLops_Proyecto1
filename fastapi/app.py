from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import mlflow
import os

# --------------------------------------------------
# Inicialización de la app FastAPI
# --------------------------------------------------
app = FastAPI(
    title="MLOps P2 Serving",
    description="API para servir el modelo entrenado y registrado en MLflow",
    version="0.1.0"
)

# --------------------------------------------------
# Modelo de entrada (features reales del dataset)
# --------------------------------------------------
class InputRow(BaseModel):
    Elevation: float
    Aspect: float
    Slope: float
    Horizontal_Distance_To_Hydrology: float
    Vertical_Distance_To_Hydrology: float
    Horizontal_Distance_To_Roadways: float
    Hillshade_9am: float
    Hillshade_Noon: float
    Hillshade_3pm: float
    Horizontal_Distance_To_Fire_Points: float
    Wilderness_Area: str
    Soil_Type: str
    # ⚠️ Cover_Type (target) no se incluye porque es lo que vamos a predecir

# --------------------------------------------------
# Configuración de MLflow (placeholder hasta entrenar)
# --------------------------------------------------
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "cover_type_model")   # nombre que usaremos al registrar
MODEL_STAGE = os.getenv("MODEL_STAGE", "Production")       # stage a servir (Staging/Production)

# Inicialmente no cargamos modelo (se conecta después al Registry)
model = None

# --------------------------------------------------
# Endpoints
# --------------------------------------------------
@app.get("/health")
def health():
    """Verifica que el servicio está activo"""
    return {"status": "ok"}

@app.post("/predict")
def predict(row: InputRow):
    """Predice la clase Cover_Type para un registro"""
    data = pd.DataFrame([row.dict()])

    if model is None:
        return {
            "prediction": None,
            "detail": f"Modelo '{MODEL_NAME}' en stage '{MODEL_STAGE}' aún no cargado."
        }

    try:
        pred = model.predict(data)
        return {"prediction": int(pred[0])}
    except Exception as e:
        return {"error": str(e)}
