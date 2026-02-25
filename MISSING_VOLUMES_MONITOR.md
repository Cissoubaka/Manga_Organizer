# 📚 Surveillance des Volumes Manquants

> **Système complet de surveillance automatique et d'envoi intelligent des téléchargements aux clients**

Cette fonctionnalité transforme Manga Organizer en une plateforme de gestion proactive de votre collection. Elle détecte automatiquement les volumes manquants, les recherche sur plusieurs sources, et peut envoyer directement les téléchargements à vos clients (qBittorrent, aMule).

---

## 🎯 Fonctionnalités

### 📊 Surveillance Intelligent
- **Détection automatique** des volumes manquants dans votre collection
- **Suivi par série** avec configuration granulaire
- **Statistiques en temps réel** : nombre de séries, volumes manquants, téléchargements

### 🔍 Recherche Multi-Sources
- **EBDZ** : Forum francophone spécialisé mangas
- **Prowlarr** : Agrégateur d'indexeurs torrent/usenet
- **Nautiljon** : Validation de l'existence du volume
- Système de **score de pertinence** pour prioriser les meilleurs résultats

### 📥 Téléchargement Automatique
- **Envoi direct à qBittorrent** avec gestion des catégories
- **Support aMule/eMule** pour les utilisateurs traditionels
- **Historique complet** des téléchargements
- Logs des succès et erreurs

### ⏰ Automatisation Configurable
- Vérification **périodique** (minutes, heures, jours)
- Activation/désactivation par série
- Mode **manuel** pour chaque recherche

---

## 🚀 Démarrage Rapide

### 1️⃣ Accéder à la Surveillance

```
Accueil → Surveillance
ou
http://localhost:5000/missing-monitor
```

### 2️⃣ Configuration Initiale

#### Configuration Générale (onglet ⚙️)

```markdown
✅ Activer la surveillance
  → Active/désactive toute la fonctionnalité

🔄 Vérification automatique
  → Intervalle : 60 minutes (configurable)
  → Exécution automatique de la surveillance

🔍 Recherche automatique
  → Active la recherche sur les sources

📥 Téléchargement automatique
  → Envoie les résultats aux clients configurés
  ⚠️ À activer avec prudence !
```

### 3️⃣ Surveiller une Série

**Onglet "Séries en Surveillance"**

```
1. Voir la liste des séries avec volumes manquants
2. Cliquer sur "Configurer" pour une série
3. Activer la surveillance
4. Valider
```

### 4️⃣ Vérification Manuelle

**Onglet "Aperçu"**

```
Bouton "Vérifier Maintenant" → Lance une vérification
→ Affiche les résultats en temps réel
→ Propose les téléchargements
```

---

## 📋 Guide des Onglets

### 📊 Aperçu

Affiche les statistiques principales :
- **Séries en Surveillance** : Nombre de séries suivies
- **Volumes Manquants** : Total global
- **Téléchargements** : Nombre de fichiers envoyés

**Actions rapides:**
- `▶️ Vérifier Maintenant` : Lance une vérification immédiate
- `🔄 Rafraîchir` : Actualise les stats
- Liste des **derniers téléchargements** avec statut

### 📖 Séries en Surveillance

Vue détaillée de toutes les séries en surveillance.

**Fonctionnalités:**
- 🔍 Recherche par titre
- Filtre par statut:
  - `Tous les statuts` : Toutes les séries
  - `Volumes manquants` : Série terminée sur Nautiljon (priorité)
  - `À compléter` : Série en cours sur Nautiljon

**Infos par carte:**
```
[Titre Manga]
📚 X volume(s) local
🌊 Y volumes (Nautiljon)
⚠️  Z manquant(s): [liste]
[Bouton Configurer]
```

### 🔍 Recherche Manuelle

Recherche un volume spécifique sur demande.

**Formulaire:**
```
📖 Titre du Manga      : [One Piece]
📚 Numéro de Volume    : [1]
🔗 Sources             : [☑ EBDZ] [☑ Prowlarr] [☑ Nautiljon]
```

**Résultats:**
```
[Titre résultat]
- 🔗 Source (EBDZ/Prowlarr)
- 👥 X seeders (si applicable)
- 💾 Taille fichier
[Bouton 📥 Télécharger]
```

**Modal de téléchargement:**
```
Lien Torrent/Magnet : [Coller lien magnet/torrent]
Titre              : [Rempli auto]
Volume             : [Rempli auto]
```

### 📜 Historique

Tous les téléchargements effectués.

**Filtres:**
- `Tous les événements`
- `✅ Succès`
- `❌ Erreurs`

**Infos par événement:**
```
✅/❌ [Titre] - Vol [N]
Client : [qBittorrent/aMule]
Message : [Détails succès/erreur]
Date : [2025-02-25 14:30]
```

### ⚙️ Configuration

Paramètres globaux de la surveillance.

**Options:**
```
✅ Activer la surveillance
   → Maître ON/OFF

🔄 Vérification automatique
   → Intervalle : [60] [minutes|heures|jours]

🔍 Recherche automatique
   → Active/désactive la recherche

🔗 Sources de Recherche
   → [☑ EBDZ] [☑ Prowlarr] [☑ Nautiljon]

📥 Téléchargement automatique
   → Envoie les résultats automatiquement

Client Préféré
   → [qBittorrent | aMule]
```

---

## 🔧 Configuration Détaillée

### Configuration EBDZ

Pour utiliser la source EBDZ, il faut d'abord configurer EBDZ:

**Settings → EBDZ Configuration:**
```
Username : [votre login]
Password : [votre mot de passe chiffré]
Forums   : [Sélectionner vos forums]
```

### Configuration Prowlarr

Pour utiliser Prowlarr:

**Settings → Prowlarr Configuration:**
```
URL        : http://127.0.0.1
Port       : 9696
API Key    : [Votre clé API]
Indexers   : [Sélectionner les indexeurs]
```

### Configuration qBittorrent

Pour envoi auto:

**Settings → qBittorrent Configuration:**
```
URL              : http://127.0.0.1
Port             : 8080
Username         : [optionnel]
Password         : [optionnel]
Catégorie défaut : [mangas]
```

### Configuration aMule

Configuration de base dans Flask config:
```python
EMULE_CONFIG = {
    'enabled': True,
    'host': '127.0.0.1',
    'port': 4711,
    'ec_port': 4712,
    'password': ''
}
```

---

## 📱 Cas Usages Typiques

### Cas 1: Surveillance Passive (Manuelle)

**Configuration:**
```
☐ Vérification automatique
☑ Recherche automatique
☐ Téléchargement automatique
```

**Workflow:**
1. Aller à "Surveillance"
2. Cliquer "Vérifier Maintenant"
3. Examiner les résultats
4. Télécharger manuellement les meilleurs

### Cas 2: Surveillance Smart

**Configuration:**
```
☑ Vérification automatique (60 min)
☑ Recherche automatique
☐ Téléchargement automatique
```

**Behavior:**
- Toutes les heures : recherche auto
- Résultats affichés instantanément
- Vous cliquez pour télécharger

### Cas 3: Automatisation Complète

**Configuration:**
```
☑ Vérification automatique (60 min)
☑ Recherche automatique
☑ Téléchargement automatique
```

**Behavior:**
- Toutes les heures : recherche + envoi auto
- Résultats dans l'historique
- Aperçu des statistiques
⚠️ **Risqué** : Vérifier régulièrement l'historique

---

## 🔐 Sécurité

### Protection des Données

- ✅ Mots de passe **chiffrés** sur disque
- ✅ Pas de lien stocké en clair
- ✅ Logs des tentatives de téléchargement
- ✅ Validation des sources Nautiljon

### API Endpoints

Tous les endpoints sont sous `/api/missing-monitor/`:

```
GET  /config                           # Charger config
POST /config                           # Sauvegarder config
GET  /series                           # Lister séries
POST /series/<id>/monitor              # Configurer série
POST /search                           # Rechercher volume
POST /download                         # Envoyer torrent
POST /run-check                        # Vérification manuelle
GET  /stats                            # Statistiques
GET  /history                          # Historique
```

---

## 🐛 Dépannage

### "Aucun résultat trouvé"

**Causes possibles:**
1. EBDZ/Prowlarr non configurés
2. Volume très récent (pas encore indexé)
3. Titre trop différent de la source
4. Source temporairement indisponible

**Solutions:**
- Vérifier les configurations EBDZ et Prowlarr
- Essayer une variante du titre
- Utiliser "Recherche Manuelle" avec lien direct

### "Erreur qBittorrent / aMule"

**Causes possibles:**
1. Client non configuré ou arrêté
2. Authentification échouée
3. Connexion réseau

**Solutions:**
- Vérifier l'état du service
- Tester la connexion avec POST /config
- Consulter les logs de Manga Organizer

### "Surveillance ne se lance pas"

**Causes possibles:**
1. Scheduler APScheduler non démarré
2. Configuration manquante
3. Erreur en base de données

**Solutions:**
- Vérifier les logs de l'application
- Redémarrer Manga Organizer
- Vérifier `missing_monitor_config.json`

### Performances Lentes

**Optimisations:**
- Réduire l'intervalle EBDZ (moins souvent)
- Désactiver les sources inutiles
- Limiter le nombre de séries en surveillance

---

## 📊 Statistiques et Historique

### Historique Automatique

Chaque action est enregistrée:
```
- Titres recherchés
- Nombre de résultats
- Client utilisé (qBit/aMule)
- Succès / Échecs
- Messages d'erreur
```

### Analyse

Via l'onglet "Historique":
- Voir les tendances
- Identifier les problèmes récurrents
- Analyser l'activité

---

## 🆘 Support et Logs

### Logs de l'Application

Se trouvent dans les logs Flask:
```bash
# Avec Docker
docker-compose logs app

# Localement
python app.py  # Voir la sortie console
```

### Messages Informatifs

L'application affiche:
```
[2025-02-25 14:30:45] 📚 Surveillance des volumes manquants en cours...
• 15 séries en surveillance
• 45 volumes manquants
• Prowlarr: 12 résultats
• EBDZ: 8 résultats
✓ Un résultat auto-envoyé à qBittorrent
```

---

## 🔄 Intégration API

### Créer une Recherche (Curl)

```bash
curl -X POST http://localhost:5000/api/missing-monitor/search \
  -H "Content-Type: application/json" \
  -d '{
    "title": "One Piece",
    "volume_num": 100,
    "sources": ["ebdz", "prowlarr"]
  }'
```

### Envoyer un Torrent (Curl)

```bash
curl -X POST http://localhost:5000/api/missing-monitor/download \
  -H "Content-Type: application/json" \
  -d '{
    "link": "magnet:?xt=urn:btih:...",
    "title": "One Piece",
    "volume_num": 100,
    "client": "qbittorrent"
  }'
```

---

## 📌 Points Importants

- **Clés de chiffrement** : Stockées dans `data/encryption_key`
- **Configuration** : Dans `data/missing_monitor_config.json`
- **Base de données** : Tables dans `manga_library.db`
- **Historique** : Tables `missing_volume_downloads`
- **Monitoring** : Table `missing_volume_monitor`

---

## 🆕 Améliorations Futures

- [ ] Support Notification Email
- [ ] Push notifications sur mobile
- [ ] Interface admin avancée
- [ ] Statistiques graphiques
- [ ] Export historique (CSV/JSON)
- [ ] Règles de filtrage avancées
- [ ] Support MyAnimeList / AniList

---

## 📝 Licence

Même licence que Manga Organizer

---

**Besoin d'aide?** Créez un issue sur GitHub ou consultez la documentation principale.
