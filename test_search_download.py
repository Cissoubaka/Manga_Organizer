#!/usr/bin/env python3
"""
Script de test pour vérifier la recherche et le téléchargement
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"
HEADERS = {"Content-Type": "application/json"}

def log(message, status="info"):
    """Afficher un message formaté"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {
        "ok": "✅",
        "error": "❌",
        "info": "ℹ️",
        "test": "🧪",
        "success": "✓",
        "warn": "⚠️"
    }
    icon = icons.get(status, "→")
    print(f"[{timestamp}] {icon} {message}")

def test_config():
    """Tester le chargement de la configuration"""
    log("Vérification de la configuration...", "test")
    
    try:
        response = requests.get(f"{BASE_URL}/api/missing-monitor/config")
        if response.status_code == 200:
            config = response.json()
            log(f"Configuration chargée", "ok")
            
            missing = config.get('monitor_missing_volumes', {})
            new = config.get('monitor_new_volumes', {})
            
            log(f"  Volumes manquants: enabled={missing.get('enabled')}, sources={missing.get('search_sources')}", "info")
            log(f"  Nouveaux volumes: enabled={new.get('enabled')}, sources={new.get('search_sources')}", "info")
            
            return config
    except Exception as e:
        log(f"Erreur configuration: {e}", "error")
    
    return None

def test_search_ebdz(title="Naruto", volume=1):
    """Tester la recherche EBDZ"""
    log(f"Test recherche EBDZ: '{title}' vol {volume}", "test")
    
    try:
        payload = {
            "title": title,
            "volume_num": volume,
            "sources": ["ebdz"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/missing-monitor/search",
            json=payload,
            headers=HEADERS
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                results = data.get('results', [])
                log(f"Résultats EBDZ: {len(results)} trouvé(s)", "ok")
                
                for i, result in enumerate(results[:3], 1):
                    log(f"  {i}. {result.get('title', 'Sans titre')[:60]}", "info")
                
                return results
            else:
                log(f"Erreur: {data.get('error')}", "error")
        else:
            log(f"HTTP {response.status_code}: {response.text[:100]}", "error")
    
    except Exception as e:
        log(f"Erreur recherche EBDZ: {e}", "error")
    
    return []

def test_search_prowlarr(title="Naruto", volume=1):
    """Tester la recherche Prowlarr"""
    log(f"Test recherche Prowlarr: '{title}' vol {volume}", "test")
    
    try:
        payload = {
            "title": title,
            "volume_num": volume,
            "sources": ["prowlarr"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/missing-monitor/search",
            json=payload,
            headers=HEADERS
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                results = data.get('results', [])
                log(f"Résultats Prowlarr: {len(results)} trouvé(s)", "ok")
                
                for i, result in enumerate(results[:3], 1):
                    seeders = result.get('seeders', 0)
                    log(f"  {i}. {result.get('title', 'Sans titre')[:60]} (seeds: {seeders})", "info")
                
                return results
            else:
                log(f"Erreur: {data.get('error')}", "error")
        else:
            log(f"HTTP {response.status_code}: {response.text[:100]}", "error")
    
    except Exception as e:
        log(f"Erreur recherche Prowlarr: {e}", "error")
    
    return []

def test_download_amule(link):
    """Tester l'envoi à aMule"""
    log(f"Test téléchargement aMule: {link[:50]}...", "test")
    
    try:
        payload = {"link": link}
        response = requests.post(
            f"{BASE_URL}/api/emule/add",
            json=payload,
            headers=HEADERS
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                log(f"aMule: {data.get('message', 'Succès')}", "ok")
                return True
            else:
                log(f"aMule: {data.get('error', 'Erreur inconnue')}", "warn")
        else:
            log(f"HTTP {response.status_code}: {response.text[:100]}", "error")
    
    except Exception as e:
        log(f"Erreur aMule: {e}", "error")
    
    return False

def test_download_qbittorrent(torrent_url):
    """Tester l'envoi à qBittorrent"""
    log(f"Test téléchargement qBittorrent: {torrent_url[:50]}...", "test")
    
    try:
        payload = {"torrent_url": torrent_url}
        response = requests.post(
            f"{BASE_URL}/api/qbittorrent/add",
            json=payload,
            headers=HEADERS
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                log(f"qBittorrent: {data.get('message', 'Succès')}", "ok")
                return True
            else:
                log(f"qBittorrent: {data.get('error', 'Erreur inconnue')}", "warn")
        else:
            log(f"HTTP {response.status_code}: {response.text[:100]}", "error")
    
    except Exception as e:
        log(f"Erreur qBittorrent: {e}", "error")
    
    return False

def main():
    """Lancer les tests"""
    print("\n" + "="*60)
    print("🧪 TEST COMPLET: Recherche et Téléchargement")
    print("="*60 + "\n")
    
    # 1. Tester la configuration
    log("=== ÉTAPE 1: Configuration ===", "info")
    config = test_config()
    
    if not config:
        log("Impossible de continuer sans configuration", "error")
        return
    
    print()
    
    # 2. Tester la recherche
    log("=== ÉTAPE 2: Recherche ===", "info")
    
    # Choisir un titre simple pour tester
    test_title = "Naruto"
    test_volume = 1
    
    print()
    ebdz_results = test_search_ebdz(test_title, test_volume)
    
    print()
    prowlarr_results = test_search_prowlarr(test_title, test_volume)
    
    print()
    
    # 3. Tester les téléchargements (avec les vrais résultats si disponibles)
    log("=== ÉTAPE 3: Téléchargement ===", "info")
    
    if ebdz_results:
        first_ebdz = ebdz_results[0]
        ed2k_link = first_ebdz.get('link', '')
        
        if ed2k_link:
            print()
            test_download_amule(ed2k_link)
        else:
            log("Aucun lien ED2K trouvé pour tester aMule", "warn")
    else:
        log("Aucun résultat EBDZ pour tester le téléchargement", "warn")
    
    if prowlarr_results:
        first_prowlarr = prowlarr_results[0]
        torrent_url = first_prowlarr.get('downloadUrl') or first_prowlarr.get('link', '')
        
        if torrent_url:
            print()
            test_download_qbittorrent(torrent_url)
        else:
            log("Aucune URL de torrent trouvée pour tester qBittorrent", "warn")
    else:
        log("Aucun résultat Prowlarr pour tester le téléchargement", "warn")
    
    print()
    print("="*60)
    print("✅ Tests terminés!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
