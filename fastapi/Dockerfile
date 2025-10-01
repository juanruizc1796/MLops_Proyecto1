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
