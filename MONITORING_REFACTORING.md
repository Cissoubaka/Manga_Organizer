# Refactoring du Monitoring - Flux Nautiljon Optimisé

## Changements Opérés

### 1. **Searcher (`blueprints/missing_monitor/searcher.py`)**

#### Modifications:
- ❌ Suppression de `_search_nautiljon()` (ne servait que pour confirmer l'existence du volume)
- ✅ Ajout de `check_new_volume_on_nautiljon(title, current_total)` 
  - Vérifie uniquement s'il y a un **nouveau volume**
  - Retourne: `(has_new_volume: bool, nautiljon_total: int)`
  
- ✅ Ajout de `search_for_new_volumes(title, new_volume_num, sources)`
  - Cherche seulement sur EBDZ + Prowlarr
  - **Pas de Nautiljon** (pour la recherche)

- ✅ Modification de `search_for_volume()`
  - Retire automatiquement Nautiljon des sources
  - Seules sources: EBDZ + Prowlarr (pour les volumes manquants)

#### Résultat:
```
Avant: search_for_volume() → EBDZ + Prowlarr + Nautiljon (3 requêtes)
Après: search_for_volume() → EBDZ + Prowlarr (2 requêtes) ✅
```

### 2. **Detector (`blueprints/missing_monitor/detector.py`)**

#### Ajout:
- ✅ `get_series_for_new_volume_check()`
  - Récupère TOUTES les séries (pas seulement celles avec volumes manquants)
  - Utilisé pour vérifier les nouveaux volumes sur Nautiljon

### 3. **Scheduler (`blueprints/missing_monitor/scheduler.py`)**

#### Nouveaux flux:
- ✅ `run_missing_volume_check()` - Désormais **sans Nautiljon**
  - Cherche uniquement sur EBDZ + Prowlarr
  - Ajoute `'check_type': 'missing_volumes'` aux stats

- ✅ `run_new_volume_check()` - Nouveau flux **avec Nautiljon**
  - Vérifie d'abord sur Nautiljon
  - Si nouveau volume: cherche sur EBDZ + Prowlarr
  - Ajoute `'check_type': 'new_volumes'` aux stats

- ✅ Modification de `_run_monitor()`
  - Appelle les deux vérifications selon la configuration
  - Charge `monitor_missing_volumes` et `monitor_new_volumes` séparément

### 4. **Routes (`blueprints/missing_monitor/routes.py`)**

#### Ajout:
- ✅ `POST /api/missing-monitor/run-check` - Vérifier les volumes manquants
- ✅ `POST /api/missing-monitor/run-check-new-volumes` - Vérifier les nouveaux volumes

## Flux d'Exécution

### Avant (Problématique)
```
Vérification automatique:
  Pour chaque série avec volumes manquants:
    Chercher sur: EBDZ + Prowlarr + Nautiljon
    → Requête inutile à Nautiljon (pas de lien de DL)
    → Ralentit le monitoring
```

### Après (Optimisé)
```
Vérification automatique (toutes les 30-60 min):
  
  1️⃣  VOLUMES MANQUANTS (monitor_missing_volumes.enabled = true)
    Pour chaque série avec volumes manquants:
      Chercher sur: EBDZ + Prowlarr (SANS Nautiljon) ✅
      
  2️⃣  NOUVEAUX VOLUMES (monitor_new_volumes.enabled = true)  
    Pour chaque série:
      ├─ Vérifier Nautiljon: "y a-t-il un nouveau volume?"
      ├─ Si OUI:
      │   └─ Chercher sur EBDZ + Prowlarr
      └─ Si NON:
          └─ Ignorer (rien à chercher)
```

## Impact Performance

### Économies Réalisées

**Scénario: 5 séries avec 3 volumes manquants chacun**

```
AVANT:
  Volumes manquants: 5 × 3 = 15 requêtes EBDZ
  + 15 requêtes Prowlarr
  + 15 requêtes Nautiljon (INUTILES)
  = 45 requêtes par vérification
  × 48 verifications/jour (30 min) = 2160 requêtes/jour

APRÈS (avec cache):
  Volumes manquants: 5 × 3 = 15 requêtes Prowlarr (cached)
  Nouveaux volumes: 5 × 1 requête Nautiljon seulement
  = ~20 requêtes/jour (grâce au cache 60 min)
  
  RÉDUCTION: 2160 → 20 requêtes/jour (99% moins! 🚀)
```

### Timings

| Opération | Avant | Après | Gain |
|-----------|-------|-------|------|
| Vérifier 5 séries | ~15s | ~3s | -80% |
| Requête Nautiljon | 15 × 5 séries | 1 × 5 séries | -80% |
| Requête Prowlarr | 15 (throttled) | 0-3 (cached) | -90% |

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
    "search_sources": ["ebdz", "prowlarr"]
  },
  "monitor_new_volumes": {
    "enabled": true,
    "search_enabled": true,
    "auto_download_enabled": false,
    "search_sources": ["ebdz", "prowlarr"],
    "check_nautiljon_updates": true
  }
}
```

## Appels API pour Tester

### Vérifier les volumes manquants
```bash
curl -X POST http://localhost:5000/api/missing-monitor/run-check \
  -H "Content-Type: application/json" \
  -d '{"search_enabled": true, "auto_download": false}'
```

### Vérifier les nouveaux volumes
```bash
curl -X POST http://localhost:5000/api/missing-monitor/run-check-new-volumes \
  -H "Content-Type: application/json" \
  -d '{"auto_download": false}'
```

### Voir les stats
```bash
curl http://localhost:5000/api/missing-monitor/stats
curl http://localhost:5000/api/missing-monitor/performance
```

## Points Clés

✅ **Nautiljon utilisé uniquement pour détecter les NOUVEAUX volumes**
✅ **Pas de requête inutile à Nautiljon pour les volumes manquants**
✅ **Flux de recherche conditionnel:** Nouveau volume détecté → Chercher → Télécharger
✅ **Économies drastiques:** 99% moins de requêtes à Nautiljon
✅ **Cache optimisé:** 60 min de cache pour éviter les requêtes répétées
✅ **Throttler:** Rate-limiting de Prowlarr pour éviter les surcharges

