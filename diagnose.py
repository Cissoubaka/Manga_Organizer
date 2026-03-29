#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier l'état de l'authentification
"""
import requests
import time
import subprocess
import json

# Démarrer le serveur
print("Démarrage du serveur...")
server = subprocess.Popen(['python3', 'app.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(4)

try:
    BASE_URL = "http://localhost:5000"
    session = requests.Session()
    
    print("\n=== TEST DIAGNOSTIQUE ===\n")
    
    # TEST 1: Vérifier le current_user avant login
    print("1. Vérifier /auth/current-user (sans auth):")
    r = session.get(f"{BASE_URL}/auth/current-user")
    print(f"   Status: {r.status_code}")
    print(f"   Body: {r.text}\n")
    
    # TEST 2: Essayer un login simple
    print("2. Essayer /auth/login (get une CSRF token généralement):")
    # D'abord GET pour avoir le formulaire (mais c'est une API JSON)
    # On doit désactiver la CSRF ou la bypass
    
    # Essayer avec X-CSRFToken header
    print("   GET /auth/login (pour voir si route existe):")
    r = session.get(f"{BASE_URL}/auth/login")
    print(f"   Status: {r.status_code}\n")
    
    # TEST 3: Essayer POST mais AVEC X-CSRFToken bypass
    print("3. POST /auth/login avec X-CSRFToken bypass:")
    login_data = {'username': 'admin','password': 'admin123'}
    headers = {'X-CSRFToken': 'bypass'}  # Essayer de bypass la CSRF
    r = session.post(f"{BASE_URL}/auth/login", json=login_data, headers=headers)
    print(f"   Status: {r.status_code}")
    print(f"   Body: {r.text[:300]}\n")
    
    # TEST 4: Vérifier les cookies de session
    print("4. Vérifier les cookies:")
    print(f"   Cookies: {session.cookies.get_dict()}\n")
    
    # TEST 5: Vérifier si /api/libraries a un @login_required visible
    print("5. Essayer /api/libraries directement:")
    r = session.get(f"{BASE_URL}/api/libraries")
    print(f"   Status: {r.status_code}")
    print(f"   Body type: {type(r.text)}")
    print(f"   First 100 chars: {r.text[:100]}\n")

finally:
    print("Arrêt du serveur...")
    server.terminate()
    server.wait()
