FROM python:3.11-slim

# Configuración básica
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Crear directorio de trabajo
WORKDIR /app

# Instalar MLflow y dependencias necesarias
RUN pip install --upgrade pip && \
    pip install mlflow boto3 pymysql

# Exponer puerto de MLflow
EXPOSE 5000

# Comando de arranque se define en docker-compose
