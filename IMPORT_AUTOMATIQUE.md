# 📦 Guide d'Import Automatique - Manga Organizer

## Résumé des Modifications

Ce document décrit le nouveau système d'import automatique de fichiers pour Manga Organizer.

### Fichiers Modifiés/Créés

#### 1. **Configuration** (`config.py`)
- Ajout du chemin `LIBRARY_IMPORT_CONFIG_FILE` pour le fichier de configuration
- Ajout de la configuration par défaut `LIBRARY_IMPORT_CONFIG` avec paramètres d'import automatique

#### 2. **Data** (`data/library_import_config.json`)
- Fichier de configuration d'import automatique avec les paramètres par défaut:
  - `auto_import_enabled`: false (désactivé par défaut)
  - `import_path`: "" (à remplir par l'utilisateur)
  - `auto_assign_enabled`: true (activé par défaut)
  - `auto_create_series`: false (création manuelle recommandée)
  - `auto_import_interval`: 60 (minutes)
  - `auto_import_interval_unit`: "minutes"

#### 3. **Scheduler** (`blueprints/library/scheduler.py`)
- Nouvelle classe `LibraryImportScheduler` pour gérer l'import automatique
- Utilise APScheduler pour planifier les tâches d'import
- Méthodes principales:
  - `add_job()`: Ajouter une tâche d'import programmée
  - `remove_job()`: Supprimer la tâche d'import
  - `_auto_import()`: Logique d'exécution de l'import automatique

#### 4. **Routes API** (`blueprints/library/routes.py`)
- Nouvelles fonctions utilitaires:
  - `load_library_import_config()`: Charger la configuration
  - `save_library_import_config()`: Sauvegarder la configuration
  - `can_auto_assign()`: Vérifie si un fichier peut être auto-assigné
  - `find_auto_assign_destination()`: Trouve la destination automatique
  - `execute_auto_import()`: Exécute l'import automatique

- Nouvelle route API:
  - `POST/GET /api/import/config`: Récupère/met à jour la configuration d'import

#### 5. **Application Principale** (`app.py`)
- Initialisation du scheduler d'import lors du démarrage
- Chargement automatique de la configuration et démarrage du scheduler si activé

#### 6. **Interface Web** (`templates/import.html`)
- Nouvelle section "Configuration de l'Import Automatique" avec:
  - Checkbox pour activer/désactiver
  - Champs de configuration (chemin, fréquence, etc.)
  - Boutons pour sauvegarder, recharger, tester

#### 7. **JavaScript** (`static/js/import.js`)
- Fonctions pour gérer l'interface:
  - `loadAutoImportConfig()`: Charger la configuration du serveur
  - `saveAutoImportConfig()`: Sauvegarder la configuration
  - `testAutoImport()`: Tester l'import automatique
  - `showAutoImportStatus()`: Afficher le statut

## Fonctionnalités

### 1. **Activation/Désactivation**
- Checkbox pour activer/désactiver l'import automatique
- La tâche est créée/supprimée au redémarrage de l'application ou après sauvegarde

### 2. **Auto-assignation**
- Détecte automatiquement le titre et le volume du fichier
- Trouve une série existante correspondante
- Crée une nouvelle série si `auto_create_series` est activé
- N'importe que les fichiers auto-assignables

### 3. **Fréquence Configurable**
- Intervalle en minutes, heures ou jours
- Peut être modifiée sans redémarrer l'application

### 4. **Gestion des Doublons**
- Les anciens fichiers sont archivés dans `_old_files/`
- Les doublons sont déplacés dans `_doublons/`
- Nettoyage automatique des répertoires vides

## Utilisation

### Configuration Basique

1.  Allez à la page **Import**
2. Remplissez la section "Configuration de l'Import Automatique":
   - Entrez le chemin du dossier d'import: ex `/home/user/Downloads/mangas_to_import`
   - Choisissez la fréquence (ex: 60 minutes)
   - Activez "Autoriser auto-assignation" pour l'auto-détection

3. Cliquez sur **Enregistrer la configuration**

### Tester l'Import Automatique

⚠️ **Important**: Le bouton **"🧪 Tester l'import automatique"** lance un **vrai import**, pas seulement un test !

1. Placez quelques fichiers dans le dossier d'import
2. Cliquez sur **Tester l'import automatique**
3. L'application va:
   - Sauvegarder votre configuration
   - Scanner le dossier
   - Auto-assigner les fichiers trouvés
   - **Importer les fichiers automatiquement**
4. Un message affichera les résultats (importés, remplacés, ignorés, etc.)

### Activer l'Auto-Exécution

1. Cochez **Activer l'import automatique**
2. Cliquez sur **Enregistrer la configuration**
3. L'application commencera à scanner et importer automatiquement selon la fréquence définie

## Architecture

```
Scheduler (APScheduler)
    ↓
_auto_import() - Exécutée périodiquement
    ↓
Scan du répertoire d'import
    ↓
Pour chaque fichier:
    - Parser le nom (volume, titre, format)
    - Vérifier si auto-assignable
    - Trouver ou créer la destination
    - Importer le fichier
    ↓
Mettre à jour les statistiques de la base de données
```

## Points Importants

### Auto-Assignation

Un fichier peut être auto-assigné si:
- ✅ Son nom de fichier contient un titre reconnaissable
- ✅ Un numéro de volume peut être extrait
- ✅ Une série existante correspond au titre (recherche case-insensitive)

Exemples de noms acceptés:
- `Demon Slayer Vol 01.cbz`
- `Attack on Titan - 15.zip`
- `Death Note 05.rar`

### Options de Configuration

| Option | Description | Défaut |
|--------|-------------|--------|
| `auto_import_enabled` | Active l'import automatique | false |
| `import_path` | Chemin du dossier à scanner | "" |
| `auto_assign_enabled` | Active l'auto-détection | true |
| `auto_create_series` | Crée les séries manquantes | false |
| `auto_import_interval` | Nombre (intervalle) | 60 |
| `auto_import_interval_unit` | Unité (minutes/hours/days) | "minutes" |

## Logs

L'application affiche des messages de progression:
```
[2024-01-15 10:30:00] 📦 Import automatique en cours...
📦 5 fichier(s) trouvé(s) pour import automatique
✓ Import automatique terminé: 3 importés, 1 remplacé, 1 ignoré, 0 erreurs
```

## Troubleshooting

### L'import ne fonctionne pas

1. Vérifiez que le chemin du dossier existe et est accessible
2. Testez avec le bouton "Tester l'import automatique"
3. Vérifiez les logs de l'application pour les erreurs

### Les fichiers ne sont pas auto-assignés

Vérifiez que:
- Les noms de fichiers incluent le titre du manga
- Les titres correspondent exactement à ceux dans la base de données
- L'option "Autoriser auto-assignation" est cochée

### Le scheduler ne démarre pas

- Vérifiez que "Activer l'import automatique" est coché
- Vérifiez les logs au démarrage de l'application
- Redémarrez l'application après modification de la configuration

## Exemple Complet d'Utilisation

```bash
# 1. Créer un dossier d'import
mkdir -p ~/Downloads/manga_import

# 2. Placer des fichiers
cp "Demon Slayer Vol 01.cbz" ~/Downloads/manga_import/

# 3. Configurer dans l'app:
# - Chemin: /home/user/Downloads/manga_import
# - Fréquence: 30 minutes
# - Auto-assignation: Activée
# - Créer séries: Activé (optionnel)

# 4. Enregistrer et l'import démarre automatiquement!
# Toutes les 30 minutes, l'app:
# - Scanne le dossier
# - Identifie les fichiers importables
# - Les importe automatiquement dans les bonnes séries
# - Nettoie les répertoires
```
