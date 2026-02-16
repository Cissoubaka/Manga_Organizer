# Guide Docker - Manga Organizer

## Installation et démarrage

### Option 1 : Avec Docker Compose (recommandé)

1. **Copier le fichier d'environnement** :
```bash
cp .env.example .env
# Éditer .env et changer SECRET_KEY pour une clé sécurisée
```

2. **Construire et démarrer l'application** :
```bash
docker compose up -d
```

3. **Accéder à l'application** :
Ouvrir `http://localhost:5000` dans votre navigateur

4. **Arrêter l'application** :
```bash
docker compose down
```

### Option 2 : Avec Docker uniquement

1. **Construire l'image** :
```bash
docker build -t manga-organizer .
```

2. **Démarrer le container** :
```bash
docker run -d \
  --name manga-organizer \
  -p 5000:5000 \
  -v "$(pwd)/data:/app/data" \
  -e SECRET_KEY="your-secret-key" \
  manga-organizer
```

3. **Accéder à l'application** :
Ouvrir `http://localhost:5000` dans votre navigateur

4. **Arrêter le container** :
```bash
docker stop manga-organizer
docker rm manga-organizer
```

## Commandes utiles

### Voir les logs
```bash
docker-compose logs -f manga-organizer
```

### Exécuter une commande dans le container
```bash
docker-compose exec manga-organizer python -c "..."
```

### Accéder à un shell dans le container
```bash
docker-compose exec manga-organizer bash
```

### Reconstruire après des changements
```bash
docker-compose up -d --build
```

## Volumes et données persistantes

Les données sont stockées dans le répertoire `./data` sur votre machine hôte. Ce répertoire contient :
- `manga_library.db` : Base de données principale
- `ebdz.db` : Base de données EBDZ
- `covers/` : Couvertures des mangas
- Fichiers de configuration JSON

Même si vous supprimez le container, ces données seront conservées.

## Configuration en production

Pour la production, modifiez dans `.env` :
1. Changez `SECRET_KEY` par une clé sécurisée
2. Changez `FLASK_ENV=production`
3. Limitez les ressources (voir docker-compose.yml)
4. Utilisez un reverse proxy (nginx) devant l'application

## Configuration aMule/eMule

Le container peut communiquer avec aMule s'exécutant sur la machine **hôte** :

### Configuration par défaut
Le `docker-compose.yml` utilise `AMULE_HOST=host.docker.internal` qui accède automatiquement à la machine hôte.

### Si aMule s'exécute ailleurs
Modifiez le `docker-compose.yml` pour spécifier l'adresse IP de la machine aMule :

```yaml
services:
  manga-organizer:
    environment:
      - AMULE_HOST=192.168.1.100  # Adresse IP de la machine aMule
```

### Ou via `.env`
Ajoutez une ligne `.env` :
```bash
AMULE_HOST=192.168.1.100
```

Puis modifiez le `docker-compose.yml`:
```yaml
environment:
  - AMULE_HOST=${AMULE_HOST:-host.docker.internal}
```

**Important** : aMule doit être configuré pour accepter les connexions externes (EC port accessible).

## Dépannage

### Erreur : "Le dossier n'existe pas" avec des espaces dans le nom

Si vous obtenez cette erreur quand vous ajoutez une bibliothèque avec des espaces (ex: "Ma Collection"), vérifiez :

**1. Chemin correct dans Docker (le plus commun)**

❌ **MAUVAIS** - Chemin de la machine hôte :
```
/media/media2/KOMGA/Ma Collection
```

✅ **BON** - Chemin du conteneur avec le volume monté :
```
/library/Ma Collection
```

Le volume dans `docker-compose.yml` :
```yaml
volumes:
  - /media/media2/KOMGA/:/library   # ← Les dossiers de /media/media2/KOMGA/ sont accessibles via /library
```

**2. Vérifiez les permissions**

Le dossier doit être lisible par Docker :
```bash
# Sur la machine hôte
ls -la /media/media2/KOMGA/
# Doit afficher vos dossiers, ex: "Ma Collection", "Mangas", etc.
```

**3. Les espaces sont supportés**

Ne pas utiliser de guillemets ou d'échappement :
- ✅ `/library/Mes Mangas`
- ✅ `/library/Ma Collection de Mangas`
- ❌ `/library/"Mes Mangas"` (incorrect avec guillemets)
- ❌ `/library/Mes%20Mangas` (pas besoin d'URL encoding)

**4. Testez l'accès du conteneur**

Ouvrez un shell dans le conteneur et vérifiez que le dossier existe :
```bash
docker-compose exec manga-organizer bash
ls -la /library/
# Doit afficher vos dossiers
```

---
```bash
sudo chown -R $(id -u):$(id -g) data/
```

### Le port 5000 est déjà utilisé
Changez le port dans docker-compose.yml :
```yaml
ports:
  - "8000:5000"  # Accès à :8000 au lieu de :5000
```

### Problème avec l'installation de `unrar`
Si vous avez une erreur `Package 'unrar' has no installation candidate` :

Le Dockerfile inclut une solution automatique :
- **p7zip-full** est toujours installé comme fallback
- Le script `docker-entrypoint.sh` tente d'installer `unrar` au démarrage
- Si `unrar` n'est pas disponible, les archives RAR seront traitées par `p7zip-full` ou `rarfile`

Si vous avez des problèmes de décompression RAR, vous pouvez :
1. Ignorer l'erreur et utiliser le container avec `p7zip-full`
2. Utiliser une image Docker alternative (par ex. Ubuntu au lieu de Debian slim)
3. Mettre à jour votre système hôte en éditant `Dockerfile` pour ajouter les dépôts `contrib` Debian


