FROM python:3.11-alpine

# Evitar la escritura de archivos .pyc y habilitar buffering para logs inmediatos
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias requeridas (oci y requests)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el script de monitoreo
COPY main.py .

CMD ["python", "main.py"]
