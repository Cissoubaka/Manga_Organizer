# Utiliser une image Debian complète pour avoir accès à plus de paquets
FROM debian:bookworm

# Installer Python et les dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    p7zip-full \
    libxml2 \
    libxslt1.1 \
    unrar-free \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Essayer d'installer amule-utils depuis les dépôts, sinon compiler
RUN apt-get update && \
    (apt-get install -y --no-install-recommends amule-utils && echo "✓ amule-utils installé depuis apt" || \
    (echo "Compilation d'aMule..." && \
    apt-get install -y --no-install-recommends \
    wget \
    build-essential \
    libssl-dev \
    pkg-config \
    autoconf \
    automake \
    libtool && \
    cd /tmp && \
    wget -q https://github.com/amule-project/amule/releases/download/2.3.3/aMule-2.3.3.tar.gz && \
    tar -xzf aMule-2.3.3.tar.gz && \
    cd aMule-2.3.3 && \
    ./configure --prefix=/usr/local --disable-gui --disable-webserver --disable-amule-daemon > /dev/null 2>&1 && \
    make -j$(nproc) > /dev/null 2>&1 && \
    make install > /dev/null 2>&1 && \
    cd / && \
    rm -rf /tmp/aMule-2.3.3* && \
    apt-get remove -y wget build-essential autoconf automake libtool && \
    rm -rf /var/lib/apt/lists/* && \
    echo "✓ aMule compilé avec succès")) && \
    which amulecmd

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
