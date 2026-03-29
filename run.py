#!/usr/bin/env python3
"""
Script d'entrée pour l'application Manga Organizer en mode production
Usage: python run.py ou FLASK_ENV=production python app.py
"""
import os
import sys
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env (dans le répertoire de l'app)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

if __name__ == '__main__':
    os.environ['FLASK_ENV'] = 'production'
    from app import create_app
    
    app = create_app('production')
    
    # Port configurable via variable d'environnement
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("Gestionnaire Multi-Bibliothèques Manga - PRODUCTION")
    print("=" * 60)
    print(f"Accédez à http://localhost:{port}")
    print("Écoute sur IPv4 uniquement")
    print("=" * 60)
    
    app.run(debug=False, host='0.0.0.0', port=port, use_reloader=False)
