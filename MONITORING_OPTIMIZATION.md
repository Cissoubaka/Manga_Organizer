# Stratégie de Monitoring Optimisée - Guide Technique

## Architecture du Monitoring

Le système de monitoring utilise un flux différencié selon le type de détection:

### Flux 1: Détection des Volumes Manquants
```
Les séries ont des volumes manquants (connus)
    ↓
Recherche directe EBDZ + Prowlarr
    ↓
Aucune requête Nautiljon (inutile)
```

**Pas de Nautiljon** - On connaît déjà les volumes manquants, pas besoin de vérifier.

### Flux 2: Détection des Nouveaux Volumes
```
Requête Nautiljon: "Y a-t-il un nouveau volume?"
    ↓
OUI: Chercher sur EBDZ + Prowlarr
NON: Ignorer (rien à chercher)
```

**Avec Nautiljon d'abord** - Vérifier qu'il existe avant de chercher.

## Problème Identifié

Avec beaucoup de séries en surveillance, le nombre de requêtes à Prowlarr peut croître rapidement:
- **10 séries × 5 volumes manquants = 50 requêtes à chaque vérification**
- Au delà d'un certain seuil, cela provoque des erreurs de rate-limiting

## Solutions Implémentées

### 1. **Throttling des Requêtes (Rate Limiting)**

**Fichier:** `blueprints/missing_monitor/request_throttler.py`

```python
RequestThrottler(requests_per_minute=30)
```

- **Limite:** 30 requêtes par minute vers Prowlarr (2 secondes entre chaque)
- **Bénéfice:** Évite les surcharges et les réponses d'erreur 429 (Too Many Requests)
- **Configuration adaptable** selon les limites de votre serveur Prowlarr

#### Avantages du Throttling:
- Requêtes bien espacées = pas de pic de charge
- Compatible avec les API externes qui ont des limites
- Pas de blocage de l'application (utilise des délais non-bloquants)

### 2. **Cache des Résultats de Recherche**

**Classe:** `SearchResultCache` (60 minutes par défaut)

```
Cache Miss (première fois):
    ┌─ Recherche Prowlarr (avec throttle)
    ├─ Stockage en cache
    └─ Retour résultat

Cache Hit (recherches suivantes):
    └─ Retour immédiat du cache
```

**Utilité:**
- Si vous vérifiez "Dragon Ball vol 5" le matin, le cache le remet l'après-midi
- Réduit drastiquement les requêtes Prowlarr
- Dure 60 minutes (configurable)

### 3. **Flux Nautiljon Optimisé**

**Ancien flux (problématique):**
```
Chercher volume manquant → Nautiljon + EBDZ + Prowlarr (3 requêtes)
```

**Nouveau flux (optimisé):**
```
Volumes manquants:
  → EBDZ + Prowlarr (aucun Nautiljon)

Nouveaux volumes:
  → Nautiljon d'abord (si nouveau → EBDZ + Prowlarr)
```

**Économies:**
- Volumes manquants: -1 requête Nautiljon par volume
- Si 10 séries × 5 volumes = 50 requêtes Nautiljon économisées

### 4. **Optimisation des Sources de Recherche**

**Classe:** `SmartSearchOptimizer`

Ordre de priorité automatique basé sur la volumétrie:

```
Peu de volumes (<20): Toutes les sources activées
  ├─ EBDZ (local, pas de limite)
  ├─ Nautiljon (confirmation rapide, NOUVEAUX VOLUMES SEULEMENT)
  └─ Prowlarr (throttled)

Beaucoup de volumes (20+): Sources optimisées
  ├─ EBDZ d'abord (local)
  └─ Prowlarr en dernier (rate-limited)
```

### 5. **Requête Optimisée à la Base de Données**

**Fichier:** `blueprints/missing_monitor/detector.py`

Changement de la requête:
```sql
-- Avant : incluait les séries non activées
LEFT JOIN missing_volume_monitor mm
WHERE (mm.enabled = 1 OR mm.id IS NULL)

-- Après : seulement les séries activées
JOIN missing_volume_monitor mm
WHERE mm.enabled = 1
```

## Configuration Recommandée

```json
{
  "enabled": true,
  "auto_check_interval": 60,
  "auto_check_interval_unit": "minutes",
  "monitor_missing_volumes": {
    "enabled": true,
    "search_enabled": true,
    "auto_download_enabled": false,
    "search_sources": ["ebdz", "prowlarr"]  // SANS nautiljon ✅
  },
  "monitor_new_volumes": {
    "enabled": true,  // Dépend de votre config
    "search_enabled": true,
    "auto_download_enabled": false,
    "search_sources": ["ebdz", "prowlarr"],  // Après vérification Nautiljon
    "check_nautiljon_updates": true  // Vérifier nouveaux volumes sur Nautiljon
  }
}
```

## Recommandations d'Usage

### Cas 1: Peu de séries (< 5 avec < 10 volumes)
```json
{
  "monitor_missing_volumes": {"enabled": true},
  "monitor_new_volumes": {"enabled": false}
}
```
- Vérifier seulement les volumes manquants
- Pas de vérification des nouveaux volumes

### Cas 2: Moyenne charge (5-15 séries)
```json
{
  "monitor_missing_volumes": {"enabled": true},
  "monitor_new_volumes": {"enabled": true},
  "auto_check_interval": 60
}
```
- Vérifications chaque heure
- EBDZ en priorité

### Cas 3: Forte charge (> 15 séries)
```json
{
  "monitor_missing_volumes": {"enabled": true},
  "monitor_new_volumes": {"enabled": false},  // Désactiver pour éviter les surcharges
  "auto_check_interval": 120
}
```
- Vérifications toutes les 2h
- Seulement les volumes manquants

## Monitoring de la Performance

### Endpoint: `/api/missing-monitor/performance`

Retourne:
```json
{
  "cache": {
    "total_entries": 42,
    "cache_size_bytes": 125000
  },
  "throttler": {
    "requests_per_minute": 30,
    "min_interval_seconds": 2.0
  }
}
```

**À vérifier:**
- `cache.total_entries` : Doit croître au fil du temps (signe du cache)
- `throttler.min_interval_seconds` : Délai entre requêtes Prowlarr

## Impact sur la Performance

### Avant Optimisation
```
5 séries × 3 volumes = 15 requêtes EBDZ + 15 Prowlarr + 15 Nautiljon = 45 requêtes
Toutes les 30 min = 1440 requêtes/jour
```

### Après Optimisation (dans les mêmes conditions)
```
Volumes manquants:
  Requête 1: 15 Prowlarr (+ cache)
  Requête 2: 0 (tout en cache)
  = ~15 requêtes/jour pour les volumes manquants

Nouveaux volumes (si activé):
  Nautiljon: 5 requêtes (une par série)
  Prowlarr: 0-5 seulement si nouveau volume trouvé
  = ~5-10 requêtes/jour pour les nouveaux volumes

Total: ~20-25 requêtes/jour au lieu de 1440 ✅
```

## Flux des Vérifications

### Vérification des Volumes Manquants

```
Detection: get_monitored_series()
  ↓
Pour chaque série avec volumes manquants:
  ├─ Pour chaque volume manquant:
  │   ├─ Vérifier cache (EBDZ + Prowlarr)
  │   ├─ Si cache miss: Throttle + search (EBDZ + Prowlarr)
  │   ├─ Mettre en cache
  │   └─ Si auto_download: envoyer au client
  └─ Mettre à jour last_checked

Duration: 2-60 secondes selon le cache
```

### Vérification des Nouveaux Volumes

```
Detection: get_series_for_new_volume_check()
  ↓
Pour chaque série:
  ├─ Vérifier Nautiljon (1 requête)
  │   ├─ Si nouveau volume trouvé:
  │   │   ├─ search_for_new_volumes() (EBDZ + Prowlarr uniquement)
  │   │   └─ Si auto_download: envoyer au client
  │   └─ Si pas nouveau: continuer
  └─ Mettre à jour last_checked

Duration: 5-15 secondes (1 requête Nautiljon par série)
```

## Dépannage

### "Too Many Requests from Prowlarr"
- Augmenter l'intervalle entre vérifications
- Vérifier: `requests_per_minute` dans le throttler  
- Réduire le nombre de séries surveillées

### Cache pas utilisé / Toujours "Cache Miss"
- Vérifier que `cache_duration_minutes` > intervalle entre vérifications
- Par défaut 60 min devrait être OK
- Les résultats expirent après 60 min

### Vérifications trop lentes
- Vérifier `/api/missing-monitor/performance`
- Si throttle enlentit trop, réduire le nombre de séries
- Désactiver les nouveaux volumes si trop de charge

## Configuration Avancée

### Modifier le Throttler

Si vous avez un serveur Prowlarr robuste:

```python
# Dans searcher.py
_throttler = RequestThrottler(requests_per_minute=60)  # Plus agressif
```

### Changer la Durée du Cache

```python
# Dans searcher.py
_cache = SearchResultCache(cache_duration_minutes=120)  # Cache plus long
```

### Désactiver le Throttle Prowlarr

```python
# Dans searcher.py - search_for_volume()
# Supprimer ces lignes:
if source == 'prowlarr':
    self._throttler.wait_if_needed('prowlarr')
```

## Améliorations Futures

1. **Requêtes Batch Prowlarr:** Chercher plusieurs volumes en une seule requête
2. **Cache Redis:** Cache distribué si infrastructure multi-serveur
3. **Priorité Dynamique:** Ajuster automatiquement selon les erreurs Prowlarr
4. **Historique de Performance:** Tracker les requêtes réussies vs échouées

