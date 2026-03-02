#!/usr/bin/env python3
"""
Script d'entrée pour l'application Manga Organizer en mode production
Usage: python run.py ou FLASK_ENV=production python app.py
"""
import os
import sys

if __name__ == '__main__':
    os.environ['FLASK_ENV'] = 'production'
    from app import create_app
    
    app = create_app('production')
    
    print("=" * 60)
    print("Gestionnaire Multi-Bibliothèques Manga - PRODUCTION")
    print("=" * 60)
    print("Accédez à http://localhost:5000")
    print("Écoute sur IPv4 et IPv6")
    print("=" * 60)
    
    app.run(debug=False, host='::', port=5000, use_reloader=False)
