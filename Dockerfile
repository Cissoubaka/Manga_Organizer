# Utiliser une image Debian complète pour avoir accès à plus de paquets
FROM debian:trixie

# Configurer les sources APT pour inclure contrib et non-free
RUN echo "deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    apt-get update -o Acquire::Retries=3 -o Acquire::http::timeout=60

# Installer Python et les dépendances système (avec retries en cas d'erreur réseau)
RUN apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    python3-lxml \
    build-essential \
    p7zip-full \
    libxml2 \
    libxml2-dev \
    libxslt1.1 \
    libxslt1-dev \
    unrar-free \
    ca-certificates \
    curl \
    wget \
    amule-utils

# Définir le répertoire de travail
WORKDIR /app

# Copier les requirements et installer les dépendances Python
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copier les fichiers Python critiques
COPY app.py .
COPY config.py .
COPY encryption.py .
COPY run.py .
COPY docker-entrypoint.sh .

# Copier les blueprints
COPY blueprints/ ./blueprints/

# Copier les dossiers statiques et templates
COPY static/ ./static/
COPY templates/ ./templates/

# Copier les autres fichiers de configuration
COPY . .

# Rendre le script d'entrypoint exécutable
RUN chmod +x docker-entrypoint.sh

# Créer les répertoires nécessaires
RUN mkdir -p data/covers

# Exposer le port de l'application
EXPOSE 5000

# Définir les variables d'environnement
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Utiliser le script d'entrypoint (exécuté en tant que root)
ENTRYPOINT ["./docker-entrypoint.sh"]
