# Proyecto

Contruir un pipeline de MLops que:
1. Ingeste datos desde una API externa (1 petición = 1 ejecución).
2. Entrene un modelo y registre métricas/artefactos en MLflow.
3. Sirva el modelo en FastAPI para hacer inferencias en línea.
4. (Bono) Exponga una UI en Streamlit para interactuar con el modelo fácilmente.

## Servicios principales

1. Airflow: Orquesta DAGs que hacen fetch → preprocess → train → log → register.
Cada ejecución del DAG es una sola petición a la API de datos.
Te asegura reproducibilidad y trazabilidad.

2. MLflow: Registra parámetros, métricas y artefactos de cada entrenamiento.
- Usa MySQL para guardar metadatos (runs, metrics, params).
- Usa MinIO como artifact store (modelos, plots, datasets).

3. MySQL: Base de datos para los metadatos de MLflow.

4. MinIO: Almacén de objetos estilo S3 para guardar los artefactos de MLflow.

5. FastAPI:
- API de inferencia: carga el último modelo de MLflow Registry.
- Expone /predict y /health.

6. Streamlit (bono) 🎨
- Interfaz gráfica simple en puerto 8503.
- Consume el endpoint /predict de FastAPI y muestra resultados.

```scss
    [Airflow DAG]
 fetch → preprocess → train → log_to_mlflow → register
                 │
                 ▼
          [MLflow Tracking]
         ├─ MySQL (metadatos)
         └─ MinIO (artefactos)
                 │
                 ▼
          [Model Registry]
                 │
                 ▼
        [FastAPI Inference API]
                 │
                 ▼
      [Streamlit UI] (opcional/bono)

```



```text
mlops-p2/
├─ airflow/              # Orquestación de pipelines
│  ├─ dags/              # DAGs de Airflow
│  ├─ logs/              # Logs de ejecución
│  ├─ plugins/           # Plugins adicionales
│  └─ requirements.txt   # Dependencias extra de Airflow
│
├─ fastapi/              # Servicio de inferencia
│  ├─ app.py             # API FastAPI (serving)
│  └─ requirements.txt   # Dependencias de FastAPI
│
├─ mlflow/               # Imagen/servidor de MLflow
│  └─ Dockerfile
│
├─ configs/              # Configuración de servicios
│  ├─ mysql-init.sql     # Script de inicialización MySQL (DB mlflow, usuario, permisos)
│  └─ .env               # (opcional) variables de entorno locales
│
├─ scripts/              # Scripts utilitarios
│  ├─ bootstrap_minio.sh # Crea bucket inicial en MinIO (mlflow)
│  └─ promote_latest.py  # Promueve mejor modelo en el Registry
│
├─ mysql_data/           # Datos persistentes de MySQL (volumen)
│
├─ ui/                   # (BONO) Interfaz Streamlit/Gradio
│  └─ app.py
│
├─ docker-compose.yml    # Orquestación de servicios en local
└─ README.md             # Documentación del proyecto

```
📌 Plan de ejecución (paso a paso)
Preparación (PASO 0–1)
Instalar Docker, crear estructura del repo, escribir docker-compose.yml.
Infra base (PASO 2)
Levantar MySQL, MinIO, MLflow, Airflow y FastAPI.
Validar que todas las UIs responden en localhost.
Pipeline en Airflow (PASO 3)
Crear DAG que ingesta, entrena y registra modelos en MLflow.
Serving en FastAPI (PASO 4)
Conectar FastAPI al Model Registry y servir el último modelo en Production.
UI en Streamlit (PASO 5 — bono)
Montar una app simple que consuma el endpoint de FastAPI.

Validación de API:

```python
import requests
URL = "http://10.43.100.103:8080/data"

resp = requests.get(URL, params={"group_number": 1})
print("Status:", resp.status_code)
print("Batch:", resp.json()["batch_number"])
print("Primeras filas:", resp.json()["data"][:2])
```

## PASO 0 - Prerrequisitos
Objetivo: Tener el ambiente local listo para correr los servicios con Docker y trabajar con Python.

1. Instalar Docker y Docker Compose
- Verifica versiones:
```bash
docker --version
docker compose version
```

2. Probar contenedores en tu máquina
```bash
docker run --rm hello-world
```

3. Python
```bash
python --version
```
4. Crear entorno virtual y instalación de librerias para el proyecto
```bash
python -m venv venv
source venv/bin/activate
pip install requests
```
## PASO 1 - Estructura inicial del proyecto

Objetivo: Crear carpetas y archivos base del repo

```bash
mkdir -p Proyecto_MLOPS/{airflow/{dags,logs,plugins},fastapi,mlflow,configs,scripts,mysql_data,ui,data}
cd Proyecto_MLOPS
```

Esto crea:
airflow/ → DAGs, logs, plugins.
fastapi/ → API de inferencia.
mlflow/ → imagen de MLflow.
configs/ → config de MySQL, .envs.
scripts/ → scripts utilitarios.
mysql_data/ → datos persistentes de MySQL.
ui/ → interfaz en Streamlit.
data/ → donde guardaremos los batches acumulados.

2. Crear script de inicialización de MySQL
Archivo: configs/mysql-init.sql

🧾 ¿Qué hace este script?
CREATE DATABASE IF NOT EXISTS mlflow ...;
Crea una base de datos llamada mlflow.
Esta BD es la que usará MLflow para guardar todos los metadatos de experimentos (runs, parámetros, métricas, rutas de artefactos).
El IF NOT EXISTS asegura que no dé error si la BD ya existe.
CREATE USER IF NOT EXISTS 'mlflow'@'%' IDENTIFIED BY 'mlflow';
Crea un usuario en MySQL llamado mlflow con contraseña mlflow.
El @'%' significa que ese usuario puede conectarse desde cualquier host (en este caso, desde el contenedor de MLflow).
Igual que antes, con IF NOT EXISTS no se rompe si ya existe.
GRANT ALL PRIVILEGES ON mlflow.* TO 'mlflow'@'%';
Le da al usuario mlflow permisos completos sobre la base de datos mlflow.
Sin esto, MLflow no podría insertar ni leer metadatos.
FLUSH PRIVILEGES;
Le dice a MySQL que recargue la tabla de usuarios y permisos para aplicar los cambios.

3. Crear airflow/requirements.txt
apache-airflow-providers-http
apache-airflow-providers-mysql
requests
pandas
scikit-learn
mlflow
boto3

4. Crear fastapi/requirements.txt
fastapi
uvicorn
pydantic
mlflow
boto3
pandas
scikit-learn

5. Crear fastapi/app.py (servicio mínimo)

🧩 Explicación general de fastapi/app.py
1. Arranca un servidor web con FastAPI
FastAPI(...) crea la aplicación web.
Esta aplicación es un servicio REST → puedes consultarlo con GET /health o POST /predict.
Es el punto de entrada para consumir tu modelo desde afuera.
2. Define la estructura de los datos de entrada
La clase InputRow(BaseModel) describe qué variables debe enviar el usuario para predecir.
En este caso son las 12 features de los batches (todo excepto Cover_Type, que es la etiqueta).
FastAPI valida automáticamente que los datos lleguen en el formato correcto (floats para numéricas, string para categorías).
3. Configura la conexión a MLflow (placeholder)
Variables:
MLFLOW_TRACKING_URI: dirección del servidor MLflow.
MODEL_NAME: nombre del modelo en el Registry (ej: "cover_type_model").
MODEL_STAGE: stage del modelo que serviremos (ej: "Production").
Por ahora model = None → significa que aún no tenemos un modelo cargado.
Más adelante, cuando registremos un modelo en MLflow, este mismo código sabrá buscarlo y cargarlo automáticamente.
4. Endpoints
GET /health
Devuelve {"status": "ok"}.
Sirve para verificar que el servicio está vivo (útil para monitoreo).
POST /predict
Recibe un JSON con las 12 features (ej: Elevation, Aspect, etc.).
Convierte los datos en un DataFrame de Pandas (porque así esperan la mayoría de modelos en MLflow).
Si no hay modelo cargado → devuelve "Modelo aún no cargado".
Cuando haya modelo cargado → ejecuta model.predict(...) y devuelve la clase predicha (Cover_Type).
🎯 En resumen
Este archivo es el servidor de predicciones.
Por ahora responde con un placeholder porque todavía no entrenamos nada.
Pero ya está estructurado para que en cuanto registres tu primer modelo en MLflow, FastAPI lo sirva sin tener que modificar nada.
👉 Así cuando avancemos en los siguientes pasos (Airflow + MLflow), no tendremos que tocar FastAPI otra vez. Solo entrenamos, registramos el modelo como "cover_type_model", lo promovemos a "Production", ¡y listo! FastAPI empezará a responder predicciones reales.

```python
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
```

crear dockerfile:

```dockerfile
FROM python:3.11-slim

# Configuración de entorno
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Crear directorio de trabajo
WORKDIR /app

# Copiar dependencias primero (para cachear instalación)
COPY requirements.txt .

# Instalar dependencias
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando de arranque (Uvicorn servidor ASGI)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

```

El docker-compose.yml que armamos es el corazón de tu infraestructura MLOps: ahí se definen todos los servicios que se levantan como contenedores, cómo se conectan y qué rol cumplen.
Te lo explico servicio por servicio:
🗄️ MySQL
mysql:
  image: mysql:8.0
  environment:
    MYSQL_ROOT_PASSWORD: root
  volumes:
    - ./mysql_data:/var/lib/mysql
    - ./configs/mysql-init.sql:/docker-entrypoint-initdb.d/mysql-init.sql:ro
Corre un contenedor con MySQL 8.0.
Guarda sus datos en ./mysql_data (persistencia local).
Ejecuta al arranque mysql-init.sql → crea la base mlflow y el usuario mlflow/mlflow.
👉 Función: es el backend de metadatos tanto para MLflow (experimentos, runs) como para Airflow (su metastore).
☁️ MinIO
minio:
  image: minio/minio:latest
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
  command: server /data --console-address ":9001"
  ports:
    - "9000:9000"
    - "9001:9001"
Almacén de objetos estilo Amazon S3, pero local.
Expuesto en:
9000 → API S3 (donde MLflow guarda artefactos).
9001 → consola web (UI de MinIO).
👉 Función: es donde MLflow guarda los modelos entrenados y otros artefactos (plots, datasets, etc.).
📊 MLflow
mlflow:
  build: ./mlflow
  command: >
    server --host 0.0.0.0 --port 5000
    --backend-store-uri mysql+pymysql://mlflow:mlflow@mysql:3306/mlflow
    --artifacts-destination s3://mlflow
Corre MLflow Tracking Server en el puerto 5000.
Usa MySQL como backend de metadatos.
Usa MinIO como artifact store (s3://mlflow).
👉 Función: guarda parámetros, métricas y modelos de cada entrenamiento → y actúa como Model Registry.
⚡ FastAPI
fastapi:
  build: ./fastapi
  environment:
    MLFLOW_TRACKING_URI: http://mlflow:5000
    MODEL_NAME: cover_type_model
    MODEL_STAGE: Production
Servicio REST de inferencia.
Construido con tu fastapi/app.py.
Conectado a MLflow (sabe qué modelo cargar desde el Model Registry).
Expone 8000 → accesible en http://localhost:8000.
👉 Función: sirve el último modelo promovido a Production.
🌀 Airflow
airflow:
  image: apache/airflow:2.8.1
  environment:
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__CORE__SQL_ALCHEMY_CONN: mysql+mysqldb://mlflow:mlflow@mysql:3306/mlflow
  volumes:
    - ./airflow/dags:/opt/airflow/dags
    - ./airflow/logs:/opt/airflow/logs
    - ./airflow/plugins:/opt/airflow/plugins
  ports:
    - "8080:8080"
Corre Airflow Webserver + Scheduler.
Usa MySQL como metastore.
Monta tus DAGs locales en /opt/airflow/dags.
Expuesto en 8080 → accesible en http://localhost:8080.
👉 Función: orquesta el pipeline de ingesta de datos → preprocesamiento → entrenamiento → registro en MLflow.
📦 Volúmenes
volumes:
  minio_data:
Persistencia de datos de MinIO.
Así, si paras el stack, los modelos guardados no se pierden.
🎯 En resumen
MySQL → metadatos (MLflow + Airflow).
MinIO → artefactos pesados (modelos, datasets).
MLflow → tracking + registro de modelos.
FastAPI → servicio de inferencia en producción.
Airflow → orquestador de todo el flujo (ingesta → entrenamiento → registro).
Todo conectado en un solo docker-compose.yml → simulando un ecosistema de producción en miniatura 🏭.