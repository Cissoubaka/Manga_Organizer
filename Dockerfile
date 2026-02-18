# Utiliser une image Debian complète pour avoir accès à plus de paquets
FROM debian:bookworm

# Configurer les sources APT pour inclure contrib et non-free
RUN echo "deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    apt-get update -o Acquire::Retries=3 -o Acquire::http::timeout=60

# Installer Python et les dépendances système (avec retries en cas d'erreur réseau)
RUN apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    p7zip-full \
    libxml2 \
    libxslt1.1 \
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

# Copier le code de l'application
COPY . .

# Copier le script d'entrypoint
COPY docker-entrypoint.sh .
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
