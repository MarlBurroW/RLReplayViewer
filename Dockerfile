FROM python:3.8-slim

# Définir des variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Définir le répertoire de travail
WORKDIR /app

# Installer les outils de développement nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Télécharger rrrocket et vérifier son contenu
RUN wget -q https://github.com/nickbabcock/rrrocket/releases/download/v0.10.4/rrrocket-0.10.4-x86_64-unknown-linux-musl.tar.gz && \
    mkdir -p /tmp/rrrocket && \
    tar -xzf rrrocket-0.10.4-x86_64-unknown-linux-musl.tar.gz -C /tmp/rrrocket && \
    ls -la /tmp/rrrocket && \
    find /tmp/rrrocket -name "rrrocket*" -type f -exec cp {} /usr/local/bin/rrrocket \; && \
    chmod +x /usr/local/bin/rrrocket && \
    rm -rf /tmp/rrrocket rrrocket-*.tar.gz

# Créer les répertoires pour les données
RUN mkdir -p /app/uploads /app/data /app/static

# Copier le code de l'application
COPY replay_analyzer/ /app/replay_analyzer/
COPY static/ /app/static/
COPY main.py .

# Exposer le port
EXPOSE $PORT

# Définir la commande de démarrage
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 