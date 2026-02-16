# 📚 Manga Organizer

> **Gestionnaire complet de collection de mangas avec recherche intégrée, importation automatique et synchronisation aMule**

Manga Organizer est une application web Flask permettant de gérer efficacement les collections de mangas numériques avec support pour :
- 📖 Gestion multi-bibliothèques
- 🔍 Recherche sur EBDZ.net (forum francophone)
- 📥 Intégration aMule/eMule pour les téléchargements
- 🎨 Interface web intuitive
- 🔐 Chiffrement des données sensibles
- 🐳 Support Docker complet

---

## 🚀 Démarrage rapide

### Avec Docker (recommandé)

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

### Système
- 512 MB RAM minimum
- 1 GB espace disque (+ taille bibliothèques)

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

### Configuration Prowlarr (optionnel)

1. **Accédez à** → `Settings` → `Prowlarr Configuration`

2. **Paramètres** :
   - **URL** : Adresse de Prowlarr (ex: http://192.168.1.100:9696)
   - **API Key** : Votre clé API Prowlarr
   - **Indexers** : Sélectionner les indexeurs à utiliser

---

## 📖 Guide d'utilisation

### 1️⃣ Créer une bibliothèque

1. Accédez à **Library** → **Add Library**
2. Entrez :
   - **Name** : Nom descriptif (ex: "Mangas français")
   - **Path** : Chemin complet vers le dossier (ex: `/media/mangas`)
   - **Description** : (optionnel)
3. Cliquez **Create**

### 2️⃣ Scanner la bibliothèque

1. Allez à **Library** → Cliquez sur votre bibliothèque
2. Cliquez **Scan Library**
3. L'app va :
   - ✅ Détecter tous les fichiers (manga, epub, pdf, rar)
   - ✅ Extraire les couvertures
   - ✅ Grouper par série
   - ✅ Détecter les volumes manquants

### 3️⃣ Importer des fichiers

1. Accédez à **Import**
2. Sélectionnez le dossier d'import (ex: dossier de téléchargements)
3. Cliquez **Scan Import Folder**
4. Cliquez **Auto-Assign** pour assigner automatiquement aux séries
5. Modifiez les assignations si nécessaire
6. Cliquez **Import** pour déplacer les fichiers

### 4️⃣ Rechercher des mangas

1. Accédez à **Search**
2. Entrez le nom du manga
3. Les résultats proviennent de la base EBDZ (si configuré)
4. Cliquez **Add** pour envoyer le lien ED2K à aMule (si connecté)

### 5️⃣ Consulter les détails

1. Allez à **Library** → **Voir une série**
2. **Onglets disponibles** :
   - **Volumes** : Tous les volumes possédés et manquants
   - **Infos** : Description, auteur, éditeur
   - **Manquants** : Recherche automatique des volumes manquants

---

## 🏗️ Architecture

### Structure du projet

```
Manga_Organizer/
├── app.py                      # Point d'entrée Flask
├── config.py                   # Configuration centralisée
├── encryption.py               # Chiffrement données sensibles
├── requirements.txt            # Dépendances Python
├── Dockerfile                  # Configuration Docker
├── docker-compose.yml          # Orchestration Docker
├── docker-entrypoint.sh        # Script démarrage container
│
├── blueprints/                 # Routes Flask (modular)
│   ├── library/               # Gestion bibliothèques
│   ├── search/                # Recherche EBDZ
│   ├── emule/                 # Intégration aMule
│   ├── ebdz/                  # Web scraping EBDZ
│   ├── prowlarr/              # Intégration Prowlarr
│   └── settings/              # Configuration
│
├── templates/                  # Pages HTML Jinja2
│   ├── index.html             # Accueil
│   ├── library.html           # Gestion bibliothèques
│   ├── search.html            # Recherche
│   ├── import.html            # Import fichiers
│   └── settings.html          # Configuration
│
├── static/                     # Ressources front-end
│   ├── css/                   # Feuilles de style
│   └── js/                    # JavaScript
│
└── data/                       # Données persistantes
    ├── manga_library.db       # Base prégnante
    ├── ebdz.db                # Cache EBDZ
    ├── *.json                 # Configurations
    └── covers/                # Couvertures extraites
```

### Technologies utilisées

- **Back-end** : Flask 3.1.2
- **Base de données** : SQLite3
- **Front-end** : HTML5, CSS3, JavaScript Vanilla
- **Images** : Pillow 12.1.0
- **Web scraping** : BeautifulSoup 4.12.2
- **Compression** : rarfile 4.1, PyPDF2 3.0.1
- **Chiffrement** : cryptography 41.0.4
- **Conteneurisation** : Docker

---

## 🐳 Docker - Guide complet

Voir [DOCKER.md](DOCKER.md) pour les détails complets sur Docker.

### Commandes essentielles

```bash
# Démarrer
docker-compose up -d --build

# Voir les logs
docker-compose logs -f manga-organizer

# Arrêter
docker-compose down

# Exécuter une commande
docker-compose exec manga-organizer bash

# Reconstruire l'image
docker-compose up -d --build --no-cache
```

### Volumes montés

- `./data:/app/data` → Données persistantes (bases, config)
- `./data/covers:/app/data/covers` → Couvertures
- `/media/media2/KOMGA/:/library` → Bibliothèques (adapter le chemin)

> ⚠️ **Important pour les chemins avec espaces en Docker**
> 
> Le chemin dans le conteneur est `/library`. Quand vous ajoutez une bibliothèque dans l'app :
> - ✅ BON : `/library/Ma Collection` ou `/library/Mes Mangas` (avec espaces supportés)
> - ❌ MAUVAIS : `/media/Ma Collection` (chemin hôte, n'existe pas dans le conteneur)
> - ❌ MAUVAIS : `/library/Ma%20Collection` (pas besoin d'encoder)
> 
> Les espaces dans les noms de dossiers sont parfaitement supportés. Si vous obtenez une erreur "Le dossier n'existe pas", vérifiez que :
> 1. Le chemin utilise `/library` (pas le chemin hôte)
> 2. Le dossier existe réellement et contient des mangas
> 3. Les permissions Docker permettent la lecture

---

## 🔒 Sécurité

### Chiffrement des données sensibles

- ✅ Mots de passe aMule/EBDZ chiffrés avec AES
- ✅ Clé de chiffrement générée automatiquement et stockée dans `data/.encryption_key`
- ✅ Variables d'environnement pour les secrets (Docker)

### Bonnes pratiques

1. **Ne jamais committer** `.env` (ignoré par `.gitignore`)
2. **Changer `SECRET_KEY`** en production (fichier `.env`)
3. **HTTPS en production** (utiliser nginx/reverse proxy)
4. **Firewall** : Limiter accès aux ports 5000 (web) et aMule (4711-4712)

---

## 📊 Formats de fichiers supportés

### Archives
- ✅ `.rar` (RAR4, RAR5)
- ✅ `.zip`
- ✅ `.7z`

### Images
- ✅ `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`

### E-books
- ✅ `.epub` (format standard)
- ✅ `.pdf` (via PyPDF2)

### Format dossier recommandé

```
Mangas/
├── "Manga Title Vol 01"
│   ├── page_001.jpg
│   ├── page_002.jpg
│   └── ...
├── "Manga Title Vol 02.zip"
├── "Manga Title Vol 03.rar"
└── ...
```

---

## 🐛 Dépannage

### amulecmd introuvable dans Docker

```bash
# Vérifier que amulecmd est installé
docker-compose exec manga-organizer which amulecmd

# Si absent, relancer avec rebuild complet
docker-compose down
docker system prune -a
docker-compose up -d --build --no-cache
```

### Erreur de permissions sur `data/`

```bash
# Sur l'hôte, fixer les permissions
sudo chown -R $USER:$USER data/
chmod -R 755 data/
```

### Port 5000 déjà utilisé

```bash
# Option 1 : Changer le port dans docker-compose.yml
ports:
  - "8000:5000"  # Accédez à :8000 au lieu de :5000

# Option 2 : Trouver quel processus utilise le port
lsof -i :5000
# Puis tuer le processus
kill -9 <PID>
```

### aMule ne se connecte pas

1. ✅ Vérifier que aMule est lancé
2. ✅ Vérifier que le EC est activé (Préférences → Connexion EC)
3. ✅ Vérifier l'IP/port dans Settings
4. ✅ Vérifier le firewall (ports 4711-4712 ouverts)
5. ✅ Tester avec : `amulecmd -h 192.168.1.234 -P password -p 4712 -c status`

### Base de données corrompue

```bash
# Sauvegarder
cp data/manga_library.db data/manga_library.db.backup

# Supprimer et recréer
rm data/manga_library.db
docker-compose restart manga-organizer

# Scanner à nouveau les bibliothèques
```

---

## 🔄 Mises à jour

```bash
# Récupérer les derniers changements
git pull origin main

# Rebuilder l'image Docker
docker-compose down
docker-compose up -d --build

# Les données seront conservées (volumes persistants)
```

---

## 📝 Développement local

```bash
# Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer dépendances
pip install -r requirements.txt

# Installer dépendances dev
pip install flask-cors flask-limiter

# Lancer en mode développement
FLASK_ENV=development FLASK_DEBUG=1 python app.py

# Application accessible à http://localhost:5000
```

---

## 📄 Fichiers importants

| Fichier | Description |
|---------|-------------|
| `app.py` | Application Flask principale |
| `config.py` | Configuration centralisée |
| `encryption.py` | Gestion chiffrement AES |
| `requirements.txt` | Dépendances Python |
| `Dockerfile` | Image Docker |
| `docker-compose.yml` | Orchestration services |
| `.env.example` | Template variables d'env |
| `DOCKER.md` | Guide Docker détaillé |

---

## 🤝 Contribution

Les contributions sont bienvenues ! Pour contribuer :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amélioration`)
3. Commit vos changements (`git commit -m 'Ajout amélioration'`)
4. Push la branche (`git push origin feature/amélioration`)
5. Ouvrir une Pull Request

---

## 📄 Licence

Ce projet est sous licence [À définir].

---

## 🆘 Support

### Problèmes connus

- ❌ EBDZ : captcha CLOUDFLARE bloque parfois le scraping
- ❌ Unicode : certains noms de mangas avec caractères spéciaux
- ⚠️ Performance : scanner 10k+ fichiers peut être lent (utiliser import par lot)

### Signaler un bug

Ouvrez une issue GitHub avec :
- Description du problème
- Logs (docker-compose logs)
- Configuration (sans données sensibles)
- Étapes pour reproduire

---

## 📚 Ressources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Docker Documentation](https://docs.docker.com/)
- [SQLite](https://www.sqlite.org/)
- [EBDZ.net](https://ebdz.net/) - Forum francophone mangas

---

## 🎯 Roadmap

- [ ] Interface API REST complète
- [ ] Support intégrations supplémentaires (Komga, etc.)
- [ ] Amélioration détection doublons
- [ ] Support multi-langue complète
- [ ] Dashboard statistiques
- [ ] Notifications temps réel

---

**Dernière mise à jour** : 16 février 2026

Fait avec ❤️ par Cissoubaka
