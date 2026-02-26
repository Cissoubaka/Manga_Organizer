#!/usr/bin/env python3
"""
Test intégré: Recherche -> Téléchargement -> Enregistrement
"""
import requests
import json
import sqlite3
from datetime import datetime

BASE_URL = "http://localhost:5000"
HEADERS = {"Content-Type": "application/json"}

def log(msg, status="info"):
    icons = {"ok": "✅", "error": "❌", "info": "ℹ️", "test": "🧪", "success": "✓"}
    print(f"[{status.upper():5}] {icons.get(status, '→')} {msg}")

print("="*70)
print("🧪 TEST INTÉGRÉ: Recherche + Téléchargement via missing-monitor")
print("="*70 + "\n")

# ÉTAPE 1: Recherche
log("Recherche de 'Naruto' vol 1 via Prowlarr...", "test")
search_payload = {
    "title": "Naruto",
    "volume_num": 1,
    "sources": ["prowlarr"]
}

response = requests.post(
    f"{BASE_URL}/api/missing-monitor/search",
    json=search_payload,
    headers=HEADERS
)

if response.status_code != 200:
    log(f"Erreur recherche: {response.status_code}", "error")
    exit(1)

results = response.json().get('results', [])
log(f"Trouvé {len(results)} résultats Prowlarr", "ok")

if not results:
    log("Pas de résultats, impossible de continuer", "error")
    exit(1)

# Prendre le premier résultat
first_result = results[0]
torrent_url = first_result.get('downloadUrl') or first_result.get('link', '')
title = first_result.get('title', 'Naruto')

log(f"Résultat sélectionné: {title[:50]}", "info")
log(f"URL: {torrent_url[:60]}...", "info")

# ÉTAPE 2: Téléchargement via missing-monitor
log("\nTéléchargement via /api/missing-monitor/download...", "test")

download_payload = {
    "link": torrent_url,
    "title": title,
    "volume_num": 1,
    "client": "qbittorrent"
}

response = requests.post(
    f"{BASE_URL}/api/missing-monitor/download",
    json=download_payload,
    headers=HEADERS
)

if response.status_code != 200:
    log(f"Erreur téléchargement: {response.status_code}", "error")
    log(f"Réponse: {response.text}", "error")
    exit(1)

dl_result = response.json()
if dl_result.get('success'):
    log(dl_result.get('message', 'Succès'), "ok")
else:
    log(f"Erreur: {dl_result.get('message')}", "error")

# ÉTAPE 3: Vérifier l'enregistrement en DB
log("\nVérification des enregistrements en base...", "test")

conn = sqlite3.connect('data/manga_library.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT id, title, volume_number, client, success, message, created_at
    FROM missing_volume_downloads
    ORDER BY created_at DESC
    LIMIT 3
""")

history = cursor.fetchall()
conn.close()

if history:
    log(f"Trouvé {len(history)} enregistrement(s)", "ok")
    print()
    for id_, title_db, vol, client, success, msg, ts in history:
        status_icon = "✓" if success else "✗"
        log(f"ID {id_} | {title_db[:40]} Vol {vol} | {client} {status_icon}", "info")
        log(f"  Message: {msg}", "info")
        log(f"  Ajouté: {ts}", "info")
else:
    log("Aucun enregistrement dans la base", "error")

print("\n" + "="*70)
log("Test terminé!", "success")
print("="*70)
