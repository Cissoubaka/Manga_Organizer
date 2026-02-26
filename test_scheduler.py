#!/usr/bin/env python3
"""
Test du scheduler de surveillance
"""
import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000"
HEADERS = {"Content-Type": "application/json"}

def log(msg, status="info"):
    icons = {"ok": "✅", "error": "❌", "info": "ℹ️", "test": "🧪", "warn": "⚠️"}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {icons.get(status, '→')} {msg}")

print("\n" + "="*70)
print("🧪 TEST SCHEDULER: Vérification de la configuration des jobs")
print("="*70 + "\n")

# ÉTAPE 1: Charger la configuration
log("Récupération de la configuration du monitoring...", "test")

response = requests.get(f"{BASE_URL}/api/missing-monitor/config")

if response.status_code != 200:
    log("Erreur: Impossible de charger la config", "error")
    exit(1)

config = response.json()
missing_cfg = config.get('monitor_missing_volumes', {})
new_cfg = config.get('monitor_new_volumes', {})

log("Configuration chargée", "ok")
log(f"  Volumes manquants:", "info")
log(f"    Activé: {missing_cfg.get('enabled')}", "info")
log(f"    Fréquence: {missing_cfg.get('check_interval')} {missing_cfg.get('check_interval_unit')}", "info")
log(f"  Nouveaux volumes:", "info")
log(f"    Activé: {new_cfg.get('enabled')}", "info")
log(f"    Fréquence: {new_cfg.get('check_interval')} {new_cfg.get('check_interval_unit')}", "info")

print()

# ÉTAPE 2: Tester une vérification manuelle
log("Exécution manuelle: Vérification des volumes manquants...", "test")

response = requests.post(f"{BASE_URL}/api/missing-monitor/run-check")

if response.status_code == 200:
    result = response.json()
    if result.get('success'):
        log(f"Vérification lancée: {result.get('message', '')}", "ok")
    else:
        log(f"Erreur: {result.get('error')}", "error")
else:
    log(f"Erreur HTTP {response.status_code}", "error")

print()

# ÉTAPE 3: Vérification des logs (si disponible)
log("Informations sur les jobs schedulés:", "test")

try:
    # On va faire une recherche manuelle pour voir l'état du système
    search_response = requests.post(
        f"{BASE_URL}/api/missing-monitor/search",
        json={
            "title": "Test",
            "volume_num": 1,
            "sources": ["ebdz"]
        },
        headers=HEADERS
    )
    
    if search_response.status_code == 200:
        log("Système de recherche: OK ✓", "info")
    else:
        log(f"Système de recherche: Erreur HTTP {search_response.status_code}", "warn")
        
except Exception as e:
    log(f"Erreur test système: {e}", "error")

print()

# ÉTAPE 4: Statistiques
log("Récupération des statistiques du monitoring...", "test")

try:
    # Tenter un POST sans paramètres pour voir l'état
    response = requests.get(
        f"{BASE_URL}/api/missing-monitor/config"
    )
    
    if response.status_code == 200:
        # Compter les séries surveillées
        config_data = response.json()
        
        log("Configuration valide et accessible", "ok")
        
        # Afficher la structure
        monitors = ['monitor_missing_volumes', 'monitor_new_volumes']
        for monitor_type in monitors:
            cfg = config_data.get(monitor_type, {})
            sources = cfg.get('search_sources', [])
            interval = cfg.get('check_interval', '?')
            unit = cfg.get('check_interval_unit', '?')
            
            monitor_name = "Volumes manquants" if 'missing' in monitor_type else "Nouveaux volumes"
            log(f"  {monitor_name}: {interval} {unit}, sources={sources}", "info")

except Exception as e:
    log(f"Erreur stats: {e}", "warn")

print("\n" + "="*70)
log("Test scheduler terminé", "ok")
print("="*70 + "\n")

# Notes
print("📋 NOTES:")
print("  • Les jobs APScheduler tournent en arrière-plan")
print("  • Utilisez /api/missing-monitor/run-check pour test manuel")
print("  • Utilisez /api/missing-monitor/run-check-new-volumes pour tester les nouveaux volumes")
print()
