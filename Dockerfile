FROM python:3.11

WORKDIR /app

# Sistem bağımlılıklarını yükle
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Gerekli Python paketlerini kopyala ve yükle
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY backend .

# Stable mount point for read-only enterprise model repositories. The host,
# orchestrator, or Kubernetes manifest supplies the actual data volume.
RUN mkdir -p /models /data/model-artifacts /data/model-scan-staging

ENV KAI_MODEL_ARTIFACT_DIR=/data/model-artifacts \
    KAI_MODEL_STAGING_DIR=/data/model-scan-staging


# Çalışma portunu belirt
EXPOSE 8000

# Uygulamayı çalıştır
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
