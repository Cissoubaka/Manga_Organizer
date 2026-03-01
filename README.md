# 📚 Manga Organizer

> **Gestionnaire complet de collection de mangas avec recherche intégrée, importation automatique et synchronisation aMule**

Manga Organizer est une application web Flask permettant de gérer efficacement les collections de mangas numériques avec support pour :
- 📖 Gestion multi-bibliothèques
- 🔍 Recherche sur EBDZ.net (forum francophone)
- 📥 Intégration aMule/eMule pour les téléchargements
- 🎨 Interface web intuitive
- 🔐 Chiffrement des données sensibles
- 🐳 Support Docker
- Support Prowlarr
- Support qBittorrent
- ajout de nouvelle série
- recherche globale de série sur l'index
- monitoring des volumes manquants/nouveaux à tester

---

## 🚀 Démarrage rapide

### Avec Docker

```bash
# 1. Cloner le projet
git clone https://github.com/Cissoubaka/Manga_Organizer.git
cd Manga_Organizer

# 2. Configurer l'environnement
cp .env.example .env
# Éditer .env et personnaliser SECRET_KEY et AMULE_HOST

# 3. Démarrer l'application
docker-compose up -d --build

# 4. Accéder à l'application
# http://localhost:5000
```

### Avec l'image Docker Hub

```bash
# 1. Cloner le projet (pour les fichiers de configuration)
git clone https://github.com/Cissoubaka/Manga_Organizer.git
cd Manga_Organizer

# 2. Configurer l'environnement
cp .env.example .env
# Éditer .env si nécessaire

# 3. Télécharger et démarrer l'image publiée
docker pull cissoubaka/manga-organizer:latest

# 4. Exécuter le conteneur
docker run -d \
  --name manga-organizer \
  -p 5000:5000 \
  -v ./data:/app/data \
  -v /path/to/library:/library \
  -e FLASK_ENV=production \
  -e SECRET_KEY=your-secret-key \
  -e AMULE_HOST=host.docker.internal \
  cissoubaka/manga-organizer:latest

# 5. Accéder à l'application
# http://localhost:5000
```

Ou avec `docker compose` en modifiant le `docker-compose.example.yml` :

```yaml
services:
  manga-organizer:
    image: cissoubaka/manga-organizer:latest  # Utiliser l'image du Hub
    # Si vous voulez construire localement, remplacez par : build: .
    container_name: manga-organizer
    # ... reste de la configuration
```
#### Commandes essentielles

```bash
# Démarrer
docker-compose up -d 

# Voir les logs
docker-compose logs -f manga-organizer

# Arrêter
docker-compose down

```
### Installation locale (sans Docker)

```bash
# 1. Cloner le projet
git clone https://github.com/Cissoubaka/Manga_Organizer.git
cd Manga_Organizer

# 2. Créer un environnement virtuel Python
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Installez les dépendances système
# Linux (Debian/Ubuntu):
sudo apt install amule-utils unrar

# 5. Démarrer l'application
python app.py

# Application accessible à http://localhost:5000
```

---

## 📋 Prérequis

### Docker (recommandé)
- Docker >= 20.10
- Docker Compose >= 1.29

### Installation locale
- Python >= 3.9
- `amule-utils` (pour intégration aMule)
- `unrar` (pour décompression archives RAR)
- Accès à un serveur aMule (optionnel)
- Accès à un serveur prowlarr (optionnel)
- Accès à un client qBittorrent (optionnel)


---

## 🔧 Configuration

### Variables d'environnement (.env)

```bash
# Clé secrète Flask - MODIFIER EN PRODUCTION
SECRET_KEY=your-secure-secret-key-here

# Mode Flask
FLASK_ENV=production

# Configuration aMule - IP de la machine exécutant aMule
# Laissez vide pour host.docker.internal (même machine que Docker)
# Mettez l'IP sinon (ex: 192.168.1.234)
AMULE_HOST=192.168.1.234
```

### Configuration aMule/eMule

1. **Accédez à l'application** → `Settings` → `aMule / eMule Configuration`

2. **Paramètres à configurer** :
   - ✅ **Enable** : Cocher pour activer l'intégration
   - **Type** : Choisir aMule (Linux/Mac) ou eMule (Windows)
   - **Host** : Adresse IP du serveur aMule (défaut: 127.0.0.1)
   - **Port** : Port EC d'aMule (défaut: 4712)
   - **Password** : Mot de passe EC d'aMule si configuré

3. **Configuration aMule côté serveur** :
   ```
   aMule → Préférences → Connexion EC
   - Activer le serveur EC
   - Port EC: 4712
   - Mot de passe: (optionnel)
   - Accepter connexions externes: OUI
   ```

4. **Test de connexion** :
   Cliquez sur le bouton "Test Connection" pour vérifier

### Configuration EBDZ.net

1. **Accédez à** → `Settings` → `EBDZ.net Configuration`

2. **Paramètres** :
   - **Username** : Votre pseudo EBDZ
   - **Password** : Votre mot de passe EBDZ
   - **Forums** : Sélectionner les sous-forums à scraper

3. **Scraper les forums** :
   - Cliquer "Scrap Selected Forums" pour indexer les liens ED2K
   - Les données seront stockées dans la base `ebdz.db`

### Configuration Prowlarr

1. **Accédez à** → `Settings` → `Prowlarr Configuration`

2. **Paramètres** :
   - **URL** : Adresse de Prowlarr (ex: http://192.168.1.100:9696)
   - **API Key** : Votre clé API Prowlarr
   - **Indexers** : Sélectionner les indexeurs à utiliser

### Configuration Qbittorrent

1. **Accédez à** → `Settings` → `Qbittorrent Configuration`

2. **Paramètres** :
   - **URL** : Adresse de Qbittorrent (ex: http://192.168.1.100:9696)
   - **Port** : configurer votre port
   - **login/mdp** : Votre login /mdp de connection à Qbittorrent


---


### 📥 Import Automatique de Fichiers

Configurez un import automatique pour que les fichiers soient importés dans vos bibliothèques selon une fréquence à choisir.

#### Configuration de l'Import Automatique

1. **Accédez à** → `Import` → Section "Configuration de l'Import Automatique" (en haut)

2. **Paramètres disponibles** :
   - **Activer l'import automatique** : Active/désactive le processus automatique
   - **Autoriser auto-assignation** : Les fichiers seront automatiquement assignés à une série existante s'ils sont reconnaissables
   - **Créer automatiquement les séries** : Crée une nouvelle série si elle n'existe pas
   - **Chemin du répertoire d'import automatique** : Dossier où placer les fichiers à importer automatiquement
   - **Fréquence d'import** : Tous les X minutes/heures/jours

#### Logique d'Auto-Assignation

Les fichiers sont auto-assignés si :
- ✅ Le nom du fichier contient un titre de série reconnaissable
- ✅ Le numéro de volume peut être extrait du nom du fichier
- ✅ Une série existante correspond au titre extrait

Exemple de noms de fichiers auto-assignables :
```
"Demon Slayer Vol 01.cbz"
"Attack on Titan - Volume 15.zip"
"Death Note 05.rar"
"One Punch Man_12.epub"
```

#### Utilisation

1. **Configurer** :
   - Définir le chemin du dossier d'import automatique
   - Choisir la fréquence (ex: toutes les heures)
   - Activer l'auto-assignation si vous le souhaitez
   - Cliquer sur "Enregistrer la configuration"

2. **Tester** :
   - Placer des fichiers dans le dossier d'import
   - Cliquer sur "Tester l'import automatique" pour vérifier
   - Les fichiers seront analysés et les auto-assignables seront identifiés

3. **Autoriser l'auto-exécution** :
   - Cocher "Activer l'import automatique"
   - L'application scanning automiquement le dossier et importe les fichiers selon la fréquence définie

#### Ce Qui Happen à l'Import

- ✅ Fichiers importés → Déplacés vers le dossier de la série
- 🔄 Fichiers remplacés → Ancien fichier archivé dans `_old_files/`
- ⏭️ Doublons ignorés → Déplacés vers `_doublons/`
- ❌ Fichiers non-assignables → Restent dans le dossier source

---

### Technologies utilisées

- **Back-end** : Flask 3.1.2
- **Base de données** : SQLite3
- **Front-end** : HTML5, CSS3, JavaScript Vanilla
- **Images** : Pillow 12.1.0
- **Web scraping** : BeautifulSoup 4.12.2
- **Compression** : rarfile 4.1, PyPDF2 3.0.1
- **Chiffrement** : cryptography 41.0.4
- **Conteneurisation** : Docker


## 📊 Formats de fichiers supportés

### Archives
- ✅ `.rar` (RAR4, RAR5)
- ✅ `.zip`
- ✅ `.7z`
- ✅ `.cbz`
- ✅ `.cbr`

### Images
- ✅ `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`

### E-books
- ✅ `.epub` (format standard)
- ✅ `.pdf` (via PyPDF2)

### Format dossier recommandé

```
Mangas/
├── "Manga Title Vol 01.zip"
├── "Manga Title Vol 02.rar"
└── ...
```